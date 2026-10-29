import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from contextbridge.engine.consolidation_queue import schedule
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.index_queue import queue_missing_indexes
from contextbridge.engine.ingestion import IngestionService
from contextbridge.models import ConsolidationJob, WorkItem
from contextbridge.persistence.consolidation_cleanup import cancel_consolidation_jobs
from contextbridge.persistence.locks import lock_owner


def dispatch_cycle(runner, publish):
    runner.refresh_configuration()
    maintain(runner)
    try:
        schedule(runner.sessions, runner.settings)
    except ModuleError as error:
        logging.getLogger(__name__).error(
            "consolidation_discovery_unavailable reason=%s", error.code
        )
    try:
        queue_missing_indexes(runner.sessions, runner.settings)
    except ModuleError as error:
        # An invalid model configuration must not stop accepted capture/outbox work.
        logging.getLogger(__name__).error("index_discovery_unavailable reason=%s", error.code)
    runner.backfill()
    return runner.dispatch(publish)


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
