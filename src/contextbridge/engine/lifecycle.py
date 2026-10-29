"""User-authorized lifecycle operations share the memory service's transaction fences."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from contextbridge.management import LifecycleResult, RetiredItem, RetiredResult
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.persistence.capture_cleanup import purge_for_memory
from contextbridge.persistence.consolidation_cleanup import purge_consolidation_for_memory
from contextbridge.persistence.index_cleanup import cancel_reindex_jobs
from contextbridge.persistence.locks import lock_owner
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryServiceError, memory_response, new_version, screen


def locked(service, memory_id, payload):
    screen(payload)
    lock_owner(service.session, service.developer_id)
    memory = service.get_memory(memory_id, lock=True)
    if (memory.scope, memory.project_id) != (payload.scope, payload.project_id):
        raise MemoryServiceError(404, "Memory not found")
    if memory.current_version != payload.expected_version:
        raise MemoryServiceError(409, "Memory changed; inspect its current version before retrying")
    return memory


def current(service, memory):
    return service.session.scalar(
        select(MemoryVersion)
        .where(MemoryVersion.memory_id == memory.id, MemoryVersion.number == memory.current_version)
        .execution_options(populate_existing=True)
    )


def retire(service, memory_id, payload):
    memory = locked(service, memory_id, payload)
    ids = service.derived_closure(memory)
    now = datetime.now(UTC)
    # Determine the complete bounded closure before mutating anything.
    for stored in service.session.scalars(
        select(Memory)
        .where(
            Memory.id.in_(ids),
            Memory.developer_id == service.developer_id,
            Memory.scope == memory.scope,
            Memory.project_id == memory.project_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all():
        if stored.retired_at is None:
            version = current(service, stored)
            if now <= version.valid_from:
                raise MemoryServiceError(409, "Memory is not yet eligible for retirement")
            version.status, version.valid_to = "SUPERSEDED", now
            stored.retired_at = now
    purge_for_memory(
        service.session,
        ids,
        developer_id=service.developer_id,
        scope=memory.scope,
        project_id=memory.project_id,
    )
    cancel_reindex_jobs(service.session, ids)
    purge_consolidation_for_memory(service.session, service.developer_id, ids)
    service.session.commit()
    return LifecycleResult(
        memory=memory_response(memory, current(service, memory)),
        retired_at=memory.retired_at,
        affected_memories=len(ids),
    )


def restore(service, memory_id, payload):
    memory = locked(service, memory_id, payload)
    if memory.retired_at is None:
        raise MemoryServiceError(
            409, "Memory is already current; inspect before retrying restoration"
        )
    # Derived summaries must be rebuilt against current sources, not resurrected from old inputs.
    derived = (
        select(MemoryEdge.id)
        .join(MemoryVersion, MemoryVersion.id == MemoryEdge.from_version_id)
        .where(MemoryVersion.memory_id == memory.id, MemoryEdge.relation == "derived_from")
        .exists()
    )
    if service.session.scalar(select(derived)):
        raise MemoryServiceError(
            409, "Restore source memories and consolidate again to rebuild this summary"
        )
    selected = service.session.scalar(
        select(MemoryVersion).where(
            MemoryVersion.memory_id == memory.id, MemoryVersion.number == payload.source_version
        )
    )
    if selected is None:
        raise MemoryServiceError(404, "Source version not found")
    previous = current(service, memory)
    now = datetime.now(UTC)
    if previous.valid_to != memory.retired_at or now <= memory.retired_at:
        raise MemoryServiceError(409, "Retirement state changed; inspect before restoring")
    memory.current_version += 1
    version = new_version(
        memory.id,
        memory.current_version,
        UpdateMemory(
            expected_version=payload.expected_version,
            content=selected.content,
            source=payload.source,
        ),
        now,
    )
    version.decision_state = (
        "contested"
        if "contested" in (selected.decision_state, previous.decision_state)
        else "clear"
    )
    service.session.add(version)
    service.session.flush()
    service.session.add(
        MemoryEdge(
            id=uuid4(), from_version_id=version.id, to_version_id=previous.id, relation="supersedes"
        )
    )
    # Keep previous.valid_to at retirement: restoration must not fill the inactive gap.
    memory.retired_at = None
    from contextbridge.persistence.related import link_related

    link_related(service.session, service.developer_id, version.id)
    service.session.commit()
    return LifecycleResult(
        memory=memory_response(memory, version), retired_at=None, affected_memories=1
    )


def retired(service, payload):
    screen(payload)
    project = (Memory.scope == "project") & (Memory.project_id == payload.project_id)
    developer = Memory.scope == "developer"
    boundary = (
        developer
        if payload.scope == "developer"
        else (or_(project, developer) if payload.include_developer else project)
    )
    stmt = (
        select(Memory, MemoryVersion)
        .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
        .where(
            Memory.developer_id == service.developer_id,
            boundary,
            Memory.retired_at.is_not(None),
            MemoryVersion.number == Memory.current_version,
            cast(Memory.conditions, JSONB).contained_by(payload.conditions),
        )
    )
    if payload.cursor is not None:
        stmt = stmt.where(Memory.id > payload.cursor)
    rows = service.session.execute(stmt.order_by(Memory.id).limit(payload.limit + 1)).all()
    return RetiredResult(
        items=[
            RetiredItem(memory=memory_response(m, v), retired_at=m.retired_at)
            for m, v in rows[: payload.limit]
        ],
        next_cursor=rows[payload.limit - 1][0].id if len(rows) > payload.limit else None,
    )
