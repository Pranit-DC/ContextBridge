from datetime import UTC, datetime

from sqlalchemy import cast, delete, select, update
from sqlalchemy.dialects.postgresql import JSONB, array

from contextbridge.background.outbox import cancel_work
from contextbridge.models import ConsolidationJob, ConsolidationSource, MemoryVersion


def cancel_consolidation_jobs(session, job_ids):
    ids = list(set(job_ids))
    for offset in range(0, len(ids), 500):
        batch = ids[offset : offset + 500]
        cancel_work(session, "consolidation", batch)
        session.execute(
            update(ConsolidationJob)
            .where(ConsolidationJob.id.in_(batch))
            .values(
                status="cancelled",
                retryable=False,
                proposals=None,
                result_memory_ids=[],
                request_fingerprint=None,
                reason_codes=["CANCELLED"],
                updated_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        session.execute(delete(ConsolidationSource).where(ConsolidationSource.job_id.in_(batch)))


def purge_consolidation_for_memory(session, developer_id, memory_ids):
    versions = select(MemoryVersion.id).where(MemoryVersion.memory_id.in_(memory_ids))
    jobs = list(
        session.scalars(
            select(ConsolidationSource.job_id).where(ConsolidationSource.version_id.in_(versions))
        ).unique()
    )
    # Jobs can also point to a forgotten summary as their result.
    ids = {str(value) for value in memory_ids}
    jobs.extend(
        session.scalars(
            select(ConsolidationJob.id).where(
                ConsolidationJob.developer_id == developer_id,
                cast(ConsolidationJob.result_memory_ids, JSONB).has_any(array(sorted(ids))),
            )
        )
    )
    cancel_consolidation_jobs(session, jobs)
