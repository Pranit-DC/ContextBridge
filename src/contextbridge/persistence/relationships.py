from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from contextbridge.engine.errors import EngineError
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.persistence.locks import lock_owner


def invalidate_derivations(session, developer_id, memory, effective, *, exclude_job_id=None):
    """Close summaries when their source changes, preserving history and original vectors.

    Caller holds the owner lock and commits atomically with its source mutation. Unlike explicit
    retirement, this does not clear unrelated buffered imports or cancel the invoking capture job.
    """
    from contextbridge.models import CaptureCandidate
    from contextbridge.persistence.capture_cleanup import cancel_capture_jobs
    from contextbridge.persistence.consolidation_cleanup import purge_consolidation_for_memory
    from contextbridge.persistence.index_cleanup import cancel_reindex_jobs
    from contextbridge.service import MemoryService

    service = MemoryService(session, developer_id)
    ids = service.derived_closure(memory) - {memory.id}
    if not ids:
        return
    rows = session.execute(
        select(Memory, MemoryVersion)
        .join(MemoryVersion)
        .where(
            Memory.id.in_(ids),
            Memory.developer_id == developer_id,
            Memory.scope == memory.scope,
            Memory.project_id == memory.project_id,
            MemoryVersion.number == Memory.current_version,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for derived, version in rows:
        if derived.retired_at is None:
            instant = max(effective, version.valid_from)
            derived.retired_at = instant
            version.valid_to, version.status = instant, "SUPERSEDED"
    selected = select(CaptureCandidate.job_id).where(
        CaptureCandidate.target_memory_id.in_(ids) | CaptureCandidate.result_memory_id.in_(ids)
    )
    if exclude_job_id is not None:
        selected = selected.where(CaptureCandidate.job_id != exclude_job_id)
    jobs = session.scalars(selected).all()
    cancel_capture_jobs(session, jobs)
    cancel_reindex_jobs(session, ids)
    purge_consolidation_for_memory(session, developer_id, ids)


def add_derivation(session, developer_id, derived_version_id, source_version_id):
    """Stage a version edge after scoped/live checks. Caller owns the transaction."""
    lock_owner(session, developer_id)
    ids = {derived_version_id, source_version_id}
    if len(ids) != 2:
        raise EngineError("INVALID_INPUT", 422)
    rows = session.execute(
        select(Memory, MemoryVersion)
        .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
        .where(
            Memory.developer_id == developer_id,
            MemoryVersion.id.in_(ids),
        )
        .order_by(Memory.id)
        .with_for_update()
    ).all()
    if len(rows) != 2:
        raise EngineError("OUT_OF_SCOPE", 404)
    (first, first_version), (second, second_version) = rows
    if (
        first.scope != second.scope
        or first.project_id != second.project_id
        or first.conditions != second.conditions
    ):
        raise EngineError("OUT_OF_SCOPE", 404)
    now = datetime.now(UTC)
    if any(
        memory.current_version != version.number
        or version.valid_from > now
        or version.valid_to is not None
        for memory, version in rows
    ):
        raise EngineError("VERSION_CONFLICT", 409)
    existing = session.scalar(
        select(MemoryEdge.id).where(
            MemoryEdge.from_version_id == derived_version_id,
            MemoryEdge.to_version_id == source_version_id,
            MemoryEdge.relation == "derived_from",
        )
    )
    if existing is None:
        session.add(
            MemoryEdge(
                id=uuid4(),
                from_version_id=derived_version_id,
                to_version_id=source_version_id,
                relation="derived_from",
            )
        )
