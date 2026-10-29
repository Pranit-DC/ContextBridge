"""Scoped transactional persistence of evidence-backed related-memory links."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from contextbridge.engine.errors import EngineError
from contextbridge.engine.related import MAX_CANDIDATES, MAX_LINKS, references
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.persistence.locks import lock_owner


def eligible(owner, now):
    return (
        select(Memory, MemoryVersion)
        .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
        .where(
            Memory.developer_id == owner,
            Memory.retired_at.is_(None),
            MemoryVersion.number == Memory.current_version,
            MemoryVersion.status == "ACTIVE",
            MemoryVersion.decision_state == "clear",
            MemoryVersion.valid_from <= now,
            MemoryVersion.valid_to.is_(None),
        )
        .execution_options(populate_existing=True)
    )


def degree(session, version_id):
    return session.scalar(
        select(func.count())
        .select_from(MemoryEdge)
        .where(
            MemoryEdge.relation == "related_to",
            or_(MemoryEdge.from_version_id == version_id, MemoryEdge.to_version_id == version_id),
        )
    )


def link_related(session, owner, version_id):
    """Stage links atomically with a write; caller commits or rolls back.

    The owner lock serializes discovery with updates, forgetting and other linkers.
    Only identical scope/project/conditions qualify. Edges contain version IDs only;
    their shared reference is reproducible from the immutable source versions.
    """
    lock_owner(session, owner)
    session.flush()
    now = datetime.now(UTC)
    source = session.execute(eligible(owner, now).where(MemoryVersion.id == version_id)).first()
    if source is None:
        return 0
    memory, version = source
    tokens = references(version.content, version.evidence)
    if not tokens:
        return 0
    candidates = session.execute(
        eligible(owner, now)
        .where(
            Memory.id != memory.id,
            Memory.scope == memory.scope,
            Memory.project_id == memory.project_id,
            cast(Memory.conditions, JSONB) == memory.conditions,
            or_(
                *(MemoryVersion.content.contains(f"`{token}`", autoescape=True) for token in tokens)
            ),
        )
        .order_by(MemoryVersion.recorded_at.desc(), MemoryVersion.id)
        .limit(MAX_CANDIDATES)
    ).all()
    count, added = degree(session, version.id), 0
    for _, peer in candidates:
        if count >= MAX_LINKS:
            break
        if not set(tokens).intersection(references(peer.content, peer.evidence)):
            continue
        # Prefer existing specific provenance/conflict/history edges over a generic link.
        pair = or_(
            (MemoryEdge.from_version_id == version.id) & (MemoryEdge.to_version_id == peer.id),
            (MemoryEdge.from_version_id == peer.id) & (MemoryEdge.to_version_id == version.id),
        )
        if session.scalar(select(MemoryEdge.id).where(pair).limit(1)) is not None:
            continue
        if degree(session, peer.id) >= MAX_LINKS:
            continue
        left, right = sorted((version.id, peer.id))
        session.add(
            MemoryEdge(id=uuid4(), from_version_id=left, to_version_id=right, relation="related_to")
        )
        session.flush()
        count, added = count + 1, added + 1
    return added


def backfill(session, owner, *, scope, project_id, after=None, limit=100):
    """One bounded, scope-bound page for existing memories; ID-only progress output."""
    if (
        type(limit) is not int
        or not 1 <= limit <= 100
        or scope not in {"project", "developer"}
        or (scope == "project" and (not isinstance(project_id, str) or not project_id))
        or (scope == "developer" and project_id is not None)
        or (after is not None and not isinstance(after, UUID))
    ):
        raise EngineError("INVALID_INPUT", 422)
    lock_owner(session, owner)
    stmt = eligible(owner, datetime.now(UTC)).where(
        Memory.scope == scope, Memory.project_id == project_id
    )
    if after is not None:
        stmt = stmt.where(Memory.id > after)
    rows = session.execute(stmt.order_by(Memory.id).limit(limit)).all()
    added = sum(link_related(session, owner, version.id) for _, version in rows)
    session.commit()
    return {
        "processed": len(rows),
        "links_created": added,
        "next_cursor": str(rows[-1][0].id) if len(rows) == limit else None,
    }
