"""One bounded current-source batch; no model calls, summaries or content copies here."""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased

from contextbridge.engine.consolidation import ConsolidationService
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.indexing import identity_fingerprint
from contextbridge.management import ConsolidationRequest, ConsolidationSubmission
from contextbridge.models import ConsolidationJob, Memory, MemoryEdge, MemoryVersion, WorkItem
from contextbridge.persistence.locks import lock_owner
from contextbridge.security import contains_secret_fields

INTERVAL_SECONDS = 900
MAX_SOURCES = 20
REVISION = "v1-current-source-consolidation-1"


def selection_id(settings, payload, ids):
    selection = {
        "scope": payload.scope,
        "project_id": payload.project_id,
        "conditions": payload.conditions,
        "ids": sorted(ids),
    }
    return uuid5(
        NAMESPACE_URL, f"{REVISION}:{settings.developer_id}:{identity_fingerprint(selection)}"
    )


def binding(model, settings):
    project = (model.scope == "project") & (model.project_id == settings.capture_project_id)
    return or_(project, model.scope == "developer") if settings.capture_allow_developer else project


def eligible(settings, now):
    previous = aliased(MemoryVersion)
    generated = (
        select(MemoryEdge.id)
        .join(previous, previous.id == MemoryEdge.from_version_id)
        .where(previous.memory_id == Memory.id, MemoryEdge.relation == "derived_from")
        .exists()
    )
    return (
        select(Memory, MemoryVersion)
        .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
        .where(
            Memory.developer_id == settings.developer_id,
            binding(Memory, settings),
            Memory.retired_at.is_(None),
            MemoryVersion.number == Memory.current_version,
            MemoryVersion.status == "ACTIVE",
            MemoryVersion.valid_to.is_(None),
            MemoryVersion.valid_from <= now,
            MemoryVersion.decision_state == "clear",
            ~generated,
        )
    )


def scoped_job(db, settings, job_id):
    job = db.scalar(
        select(ConsolidationJob).where(
            ConsolidationJob.id == job_id,
            ConsolidationJob.developer_id == settings.developer_id,
            binding(ConsolidationJob, settings),
        )
    )
    if job is None:
        raise EngineError("OUT_OF_SCOPE", 404)
    return job


def submit(db, settings, payload):
    if contains_secret_fields(payload.model_dump(mode="json")):
        raise EngineError("INVALID_INPUT", 422)
    allowed = (
        payload.scope == "project" and payload.project_id == settings.capture_project_id
    ) or (payload.scope == "developer" and settings.capture_allow_developer)
    if not allowed:
        raise EngineError("OUT_OF_SCOPE", 404)
    lock_owner(db, settings.developer_id)
    stmt = eligible(settings, datetime.now(UTC)).where(
        Memory.scope == payload.scope,
        Memory.project_id == payload.project_id,
        cast(Memory.conditions, JSONB) == payload.conditions,
    )
    if payload.version_ids is not None:
        if len(set(payload.version_ids)) != len(payload.version_ids):
            raise EngineError("INVALID_INPUT", 422)
        stmt = stmt.where(MemoryVersion.id.in_(payload.version_ids))
    rows = db.execute(stmt.order_by(MemoryVersion.id).limit(MAX_SOURCES)).all()
    if payload.version_ids is not None and len(rows) != len(payload.version_ids):
        raise EngineError("VERSION_CONFLICT", 409)
    if len(rows) < 2:
        db.commit()
        return ConsolidationSubmission(status="not_needed", source_count=len(rows))
    ids = [str(v.id) for _, v in rows]
    request_id = selection_id(settings, payload, ids)
    existing = db.scalar(
        select(ConsolidationJob).where(
            ConsolidationJob.developer_id == settings.developer_id,
            ConsolidationJob.request_id == request_id,
        )
    )
    if existing is not None:
        work_id = db.scalar(
            select(WorkItem.id).where(
                WorkItem.kind == "consolidation", WorkItem.job_id == existing.id
            )
        )
        db.commit()
        return ConsolidationSubmission(
            status=existing.status, job_id=existing.id, work_id=work_id, source_count=len(rows)
        )
    try:
        job_id = ConsolidationService(db, settings).enqueue(
            {
                "schema_version": 1,
                **payload.model_dump(mode="json", exclude={"version_ids"}),
                "query": "consolidate",
            },
            ids,
            str(request_id),
        )
    except ModuleError as error:
        raise EngineError(
            error.code, 409 if error.code == "VERSION_CONFLICT" else 422, retryable=error.retryable
        ) from None
    work_id = db.scalar(
        select(WorkItem.id).where(WorkItem.kind == "consolidation", WorkItem.job_id == job_id)
    )
    return ConsolidationSubmission(
        status="queued", job_id=job_id, work_id=work_id, source_count=len(rows)
    )


def schedule(sessions, settings, *, now=None):
    if (
        not settings.consolidation_enabled
        or settings.embedding_only
        or not (
            settings.formation_enabled or settings.integration_factory or settings.worker_factory
        )
    ):
        return 0
    now = now or datetime.now(UTC)
    with sessions() as db:
        lock_owner(db, settings.developer_id)
        recent = (
            select(ConsolidationJob.id)
            .where(
                ConsolidationJob.developer_id == settings.developer_id,
                binding(ConsolidationJob, settings),
                ConsolidationJob.updated_at > now - timedelta(seconds=INTERVAL_SECONDS),
            )
            .exists()
        )
        if db.scalar(select(recent)):
            return 0
        # Group in SQL before the limit; one sparse bucket cannot starve the other conditions.
        conditions = cast(Memory.conditions, JSONB)
        buckets = db.execute(
            eligible(settings, now)
            .with_only_columns(Memory.scope, Memory.project_id, conditions)
            .group_by(Memory.scope, Memory.project_id, conditions)
            .having(func.count() >= 2)
            .order_by(Memory.scope, Memory.project_id, conditions)
            .limit(20)
        ).all()
        for scope, project_id, values in buckets:
            payload = ConsolidationRequest(scope=scope, project_id=project_id, conditions=values)
            ids = list(
                db.scalars(
                    eligible(settings, now)
                    .with_only_columns(MemoryVersion.id)
                    .where(
                        Memory.scope == scope,
                        Memory.project_id == project_id,
                        cast(Memory.conditions, JSONB) == values,
                    )
                    .order_by(MemoryVersion.id)
                    .limit(MAX_SOURCES)
                )
            )
            existing = db.scalar(
                select(ConsolidationJob.id).where(
                    ConsolidationJob.developer_id == settings.developer_id,
                    ConsolidationJob.request_id
                    == selection_id(settings, payload, [str(i) for i in ids]),
                )
            )
            if existing is not None:
                continue  # Keep the owner lock until choosing one previously unattempted batch.
            result = submit(db, settings, payload.model_copy(update={"version_ids": ids}))
            if result.status == "queued":
                # A committed durable job is the restart-safe interval marker.
                return 1
        return 0
