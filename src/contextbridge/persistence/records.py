from datetime import UTC, datetime

from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from contextbridge.contracts import MemoryRecord
from contextbridge.models import Memory, MemoryVersion
from contextbridge.service import memory_response


def scoped_versions(developer_id, scope, project_id, instant, conditions=None):
    stmt = (
        select(Memory, MemoryVersion)
        .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
        .where(
            Memory.developer_id == developer_id,
            Memory.scope == scope,
            Memory.project_id == project_id,
            MemoryVersion.valid_from <= instant,
            or_(MemoryVersion.valid_to.is_(None), MemoryVersion.valid_to > instant),
        )
    )
    if conditions is not None:
        stmt = stmt.where(cast(Memory.conditions, JSONB).contained_by(conditions))
    return stmt


def record_response(memory, version) -> MemoryRecord:
    return MemoryRecord(
        memory=memory_response(memory, version),
        claim_key=memory.claim_key,
        confidence=version.confidence,
        decision_state=version.decision_state,
    )


def current_records(session, developer_id, candidate, *, limit=200, semantic=False):
    now = datetime.now(UTC)
    # Include the version applicable at the candidate's effective time for temporal comparison.
    stmt = (
        select(Memory, MemoryVersion)
        .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
        .where(
            Memory.developer_id == developer_id,
            Memory.scope == candidate.scope,
            Memory.project_id == candidate.project_id,
            or_(
                (MemoryVersion.valid_from <= now)
                & (MemoryVersion.valid_to.is_(None) | (MemoryVersion.valid_to > now)),
                (MemoryVersion.valid_from <= candidate.valid_from)
                & (
                    MemoryVersion.valid_to.is_(None)
                    | (MemoryVersion.valid_to > candidate.valid_from)
                ),
            ),
        )
    )
    # A claim label selects comparison candidates, never establishes their relationship.
    if semantic:
        stmt = stmt.where(
            Memory.type == candidate.type,
            cast(Memory.conditions, JSONB) == candidate.conditions,
        )
    elif candidate.claim_key is not None:
        stmt = stmt.where(
            or_(Memory.claim_key == candidate.claim_key, MemoryVersion.content == candidate.content)
        )
    else:
        stmt = stmt.where(MemoryVersion.content == candidate.content)
    rows = session.execute(stmt.order_by(Memory.id, MemoryVersion.number).limit(limit + 1)).all()
    return rows
