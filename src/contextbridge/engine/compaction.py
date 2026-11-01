"""Explicit exact-claim compaction, never semantic merging or evidence deletion."""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import or_, select

from contextbridge.engine.lifecycle import current, locked, retire_set
from contextbridge.management import CompactionResult, RetireMemory
from contextbridge.models import Memory, MemoryEdge, MemoryVersion, VersionProvenance
from contextbridge.persistence.records import record_response
from contextbridge.service import MemoryServiceError, screen


def prepare(service, payload, *, semantic=False):
    screen(payload)
    refs = [payload.keep, *payload.retire]
    ids = [ref.memory_id for ref in refs]
    if len(set(ids)) != len(ids):
        raise MemoryServiceError(422, "Choose distinct memories")
    rows = []
    now = datetime.now(UTC)
    for ref in refs:
        memory = locked(
            service,
            ref.memory_id,
            RetireMemory(
                scope=payload.scope,
                project_id=payload.project_id,
                expected_version=ref.expected_version,
            ),
        )
        version = current(service, memory)
        if (
            memory.retired_at is not None
            or memory.type not in {"FACT", "PREFERENCE", "DECISION"}
            or version.status != "ACTIVE"
            or version.decision_state != "clear"
            or version.valid_from >= now
            or version.valid_to is not None
            or not version.evidence
        ):
            raise MemoryServiceError(
                409, "Choose current clear source facts, preferences or decisions"
            )
        rows.append((memory, version))
    keeper, kept_version = rows[0]

    def signature(m, v):
        return m.type, m.conditions, m.claim_key, None if semantic else v.content, v.confidence

    if any(signature(m, v) != signature(keeper, kept_version) for m, v in rows[1:]):
        raise MemoryServiceError(409, "Compaction requires identical claims, types and conditions")
    temporal = []
    for _, version in rows:
        extension = service.session.scalar(
            select(VersionProvenance)
            .where(VersionProvenance.version_id == version.id)
            .execution_options(populate_existing=True)
        )
        temporal.append(extension.metadata_json.get("temporal") if extension else None)
    if any(value != temporal[0] for value in temporal[1:]):
        raise MemoryServiceError(409, "Inspect memories with different time precision individually")
    versions = select(MemoryVersion.id).where(MemoryVersion.memory_id.in_(ids))
    if service.session.scalar(
        select(MemoryEdge.id)
        .where(
            or_(
                (MemoryEdge.relation == "derived_from") & MemoryEdge.from_version_id.in_(versions),
                (MemoryEdge.relation == "contradicts")
                & or_(
                    MemoryEdge.from_version_id.in_(versions),
                    MemoryEdge.to_version_id.in_(versions),
                ),
            )
        )
        .limit(1)
    ):
        raise MemoryServiceError(409, "Inspect derived or conflicting memories individually")
    affected = set()
    for memory, _ in rows[1:]:
        affected.update(service.derived_closure(memory))
        if len(affected) > 200:
            raise MemoryServiceError(409, "Compaction exceeds its bounded cleanup limit")
    if keeper.id in affected:
        raise MemoryServiceError(409, "The retained claim depends on a selected duplicate")
    closure = service.session.scalars(
        select(Memory)
        .where(Memory.id.in_(affected), Memory.developer_id == service.developer_id)
        .order_by(Memory.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    snapshots = [record_response(m, v).model_dump(mode="json") for m, v in rows]
    snapshots += [
        {
            "record": record_response(m, current(service, m)).model_dump(mode="json"),
            "retired_at": m.retired_at.isoformat() if m.retired_at else None,
        }
        for m in closure
    ]
    revision = hashlib.sha256(
        json.dumps([snapshots, temporal], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result = CompactionResult(
        applied=False,
        plan_revision=revision,
        kept_memory_id=keeper.id,
        redundant_memory_ids=ids[1:],
        affected_memory_ids=sorted(affected),
    )
    return result, snapshots[: len(rows)], keeper, affected


def compact(service, payload):
    result, _, keeper, affected = prepare(service, payload)
    if payload.confirm:
        if payload.plan_revision != result.plan_revision:
            raise MemoryServiceError(409, "Preview the current compaction plan before confirming")
        retire_set(service, keeper, affected, datetime.now(UTC))
        result.applied = True
    service.session.commit()
    return result
