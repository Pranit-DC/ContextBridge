"""Remove content-bearing capture artifacts while retaining cancellation identities."""

from datetime import UTC, datetime

from sqlalchemy import select, update

from contextbridge.background.outbox import cancel_work
from contextbridge.models import CaptureCandidate, CaptureEvent, CaptureJob


def cancel_capture_jobs(session, job_ids, now=None):
    now = now or datetime.now(UTC)
    job_ids = list(set(job_ids))
    # A frozen extraction shares context. Erase the entire group when any source is removed.
    # Discovery must be bounded too: a scope can contain 100,000 captures, beyond
    # PostgreSQL's 65,535 bind-parameter limit even before the chunked erasure below.
    leaders = set()
    for offset in range(0, len(job_ids), 500):
        leaders.update(
            session.scalars(
                select(CaptureJob.group_leader_id).where(
                    CaptureJob.id.in_(job_ids[offset : offset + 500]),
                    CaptureJob.group_leader_id.is_not(None),
                )
            ).all()
        )
    related = set(job_ids)
    leaders = list(leaders)
    for offset in range(0, len(leaders), 500):
        related.update(
            session.scalars(
                select(CaptureJob.id).where(
                    CaptureJob.group_leader_id.in_(leaders[offset : offset + 500])
                )
            ).all()
        )
    job_ids = list(related)
    for offset in range(0, len(job_ids), 500):
        batch = job_ids[offset : offset + 500]
        cancel_work(session, "capture", batch)
        event_ids = select(CaptureJob.event_record_id).where(CaptureJob.id.in_(batch))
        session.execute(
            update(CaptureEvent)
            .where(CaptureEvent.id.in_(event_ids))
            .values(payload=None, fingerprint=None)
            .execution_options(synchronize_session=False)
        )
        session.execute(
            update(CaptureCandidate)
            .where(CaptureCandidate.job_id.in_(batch))
            .values(
                payload=None,
                fingerprint=None,
                admission=None,
                plan=None,
                status="cancelled",
                reason_codes=["CANCELLED"],
                target_memory_id=None,
                result_memory_id=None,
                result_version_id=None,
                comparison_version_ids=[],
            )
            .execution_options(synchronize_session=False)
        )
        session.execute(
            update(CaptureJob)
            .where(CaptureJob.id.in_(batch))
            .values(
                status="cancelled",
                retryable=False,
                reason_codes=["CANCELLED"],
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )


def expire_candidates(session, developer_id, scope_filter, now):
    scoped_jobs = (
        select(CaptureJob.id)
        .join(CaptureEvent, CaptureJob.event_record_id == CaptureEvent.id)
        .where(
            CaptureEvent.developer_id == developer_id,
            scope_filter,
        )
    )
    expired = session.scalars(
        select(CaptureCandidate.job_id).where(
            CaptureCandidate.job_id.in_(scoped_jobs),
            CaptureCandidate.payload.is_not(None),
            CaptureCandidate.expires_at <= now,
            CaptureCandidate.status.in_(["pending", "deferred"]),
        )
    ).all()
    cancel_capture_jobs(session, expired, now)
    session.execute(
        update(CaptureCandidate)
        .where(
            CaptureCandidate.job_id.in_(scoped_jobs),
            CaptureCandidate.payload.is_not(None),
            CaptureCandidate.expires_at <= now,
        )
        .values(payload=None, fingerprint=None, admission=None, plan=None)
        .execution_options(synchronize_session=False)
    )


def purge_for_memory(session, memory_ids, *, developer_id, scope, project_id):
    jobs = session.scalars(
        select(CaptureCandidate.job_id).where(
            CaptureCandidate.target_memory_id.in_(memory_ids)
            | CaptureCandidate.result_memory_id.in_(memory_ids)
        )
    ).all()
    # Before extraction there is no reliable fact-to-transcript provenance. Conservatively
    # erase this scope's buffers so an in-flight interpretation cannot recreate forgotten text.
    scoped_jobs = session.scalars(
        select(CaptureJob.id)
        .join(CaptureEvent, CaptureEvent.id == CaptureJob.event_record_id)
        .where(
            CaptureEvent.developer_id == developer_id,
            CaptureEvent.scope == scope,
            CaptureEvent.project_id == project_id,
            CaptureEvent.payload.is_not(None)
            | select(CaptureCandidate.id)
            .where(CaptureCandidate.job_id == CaptureJob.id, CaptureCandidate.payload.is_not(None))
            .exists(),
        )
    ).all()
    jobs.extend(scoped_jobs)
    cancel_capture_jobs(session, jobs)
