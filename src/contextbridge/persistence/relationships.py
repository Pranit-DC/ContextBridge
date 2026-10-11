from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from contextbridge.engine.errors import EngineError
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.persistence.locks import lock_owner


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
