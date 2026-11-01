from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update

from contextbridge.models import WorkItem


def enqueue_work(session, kind, job_id, developer_id, scope, project_id):
    """Caller commits this ID-only outbox with the domain job in one transaction."""
    existing = session.scalar(
        select(WorkItem).where(WorkItem.kind == kind, WorkItem.job_id == job_id)
    )
    if existing is not None:
        return existing.id
    now = datetime.now(UTC)
    item = WorkItem(
        id=uuid4(),
        kind=kind,
        job_id=job_id,
        developer_id=developer_id,
        scope=str(scope),
        project_id=project_id,
        available_at=now,
        updated_at=now,
    )
    session.add(item)
    return item.id


def cancel_work(session, kind, job_ids):
    session.execute(
        update(WorkItem)
        .where(WorkItem.kind == kind, WorkItem.job_id.in_(job_ids))
        .values(
            status="cancelled",
            reason_code="CANCELLED",
            lease_token=None,
            lease_until=None,
            duration_ms=None,
            updated_at=datetime.now(UTC),
        )
        .execution_options(synchronize_session=False)
    )


class FenceLost(Exception):
    """Internal cancellation; never turns a newer owner's domain job into failure."""


def check_fence(session, item_id, token, *, allow_expired=False):
    # Domain engines already hold the owner lock before checking the execution lease.
    item = session.scalar(
        select(WorkItem)
        .where(WorkItem.id == item_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        item is None
        or item.status != "running"
        or item.lease_token != token
        or (not allow_expired and item.lease_until <= datetime.now(UTC))
    ):
        raise FenceLost()
