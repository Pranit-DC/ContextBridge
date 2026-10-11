from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from contextbridge.engine.ingestion import IngestionService
from contextbridge.models import ConsolidationJob, WorkItem
from contextbridge.persistence.consolidation_cleanup import cancel_consolidation_jobs
from contextbridge.persistence.locks import lock_owner


def maintain(runner):
    with runner.sessions() as session:
        lock_owner(session, runner.settings.developer_id)
        now = datetime.now(UTC)
        if runner.settings.capture_project_id is not None:
            IngestionService(session, runner.settings)._expire(now)
        expired = session.scalars(
            select(ConsolidationJob.id)
            .where(
                ConsolidationJob.developer_id == runner.settings.developer_id,
                runner.binding(ConsolidationJob),
                ConsolidationJob.expires_at <= now,
                ConsolidationJob.status.not_in(["succeeded", "cancelled"]),
            )
            .order_by(ConsolidationJob.expires_at)
            .limit(100)
        ).all()
        cancel_consolidation_jobs(session, expired)
        cutoff = now - timedelta(seconds=runner.settings.worker_diagnostic_retention_seconds)
        ids = (
            select(WorkItem.id)
            .where(
                WorkItem.developer_id == runner.settings.developer_id,
                runner.binding(WorkItem),
                WorkItem.status.in_(["succeeded", "failed", "deferred", "cancelled"]),
                WorkItem.updated_at <= cutoff,
            )
            .order_by(WorkItem.updated_at)
            .limit(100)
        )
        session.execute(delete(WorkItem).where(WorkItem.id.in_(ids)))
        session.commit()
