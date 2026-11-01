from datetime import UTC, datetime

from sqlalchemy import delete, select, update

from contextbridge.background.outbox import cancel_work
from contextbridge.models import MemoryVersion, ReindexJob, ReindexTarget


def cancel_reindex_jobs(session, memory_ids):
    versions = select(MemoryVersion.id).where(MemoryVersion.memory_id.in_(memory_ids))
    jobs = list(
        session.scalars(
            select(ReindexTarget.job_id).where(ReindexTarget.version_id.in_(versions))
        ).unique()
    )
    for offset in range(0, len(jobs), 500):
        batch = jobs[offset : offset + 500]
        cancel_work(session, "reindex", batch)
        session.execute(
            update(ReindexJob)
            .where(ReindexJob.id.in_(batch))
            .values(
                status="cancelled",
                reason_codes=["CANCELLED"],
                retryable=False,
                request_fingerprint=None,
                updated_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        session.execute(delete(ReindexTarget).where(ReindexTarget.job_id.in_(batch)))
