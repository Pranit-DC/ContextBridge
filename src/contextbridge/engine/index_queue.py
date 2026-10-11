"""Recoverable current-version indexing; durable versions are the source of queued work."""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select

from contextbridge.engine.errors import EngineError
from contextbridge.engine.indexing import IndexService
from contextbridge.models import Memory, MemoryEmbedding, MemoryVersion, ReindexJob, ReindexTarget
from contextbridge.persistence.locks import lock_owner


def queue_missing_indexes(sessions, settings):
    if not settings.integration_factory or settings.embedding_model_id is None:
        return 0
    owner, model = settings.developer_id, settings.embedding_model_id
    with sessions() as db:
        lock_owner(db, owner)
        binding = (Memory.scope == "project") & (Memory.project_id == settings.capture_project_id)
        if settings.capture_allow_developer:
            binding = or_(binding, Memory.scope == "developer")
        indexed = (
            select(MemoryEmbedding.version_id)
            .where(
                MemoryEmbedding.version_id == MemoryVersion.id,
                MemoryEmbedding.developer_id == owner,
                MemoryEmbedding.model_id == model,
            )
            .exists()
        )
        queued = (
            select(ReindexTarget.version_id)
            .join(ReindexJob, ReindexTarget.job_id == ReindexJob.id)
            .where(
                ReindexTarget.version_id == MemoryVersion.id,
                ReindexJob.developer_id == owner,
                ReindexJob.model_id == model,
            )
            .exists()
        )
        rows = db.execute(
            select(Memory.scope, Memory.project_id, Memory.conditions, MemoryVersion.id)
            .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
            .where(
                Memory.developer_id == owner,
                binding,
                MemoryVersion.number == Memory.current_version,
                MemoryVersion.status == "ACTIVE",
                ~indexed,
                ~queued,
            )
            .order_by(MemoryVersion.id)
            .limit(100)
        ).all()
        db.commit()
    count = 0
    for scope, project, conditions, version_id in rows:
        request_id = uuid5(NAMESPACE_URL, f"contextbridge:index:{model}:{version_id}")
        with sessions() as db:
            try:
                IndexService(db, owner).enqueue(
                    {
                        "schema_version": 1,
                        "scope": scope,
                        "project_id": project,
                        "conditions": conditions,
                        "query": "index",
                        "as_of": None,
                    },
                    [str(version_id)],
                    model,
                    settings.embedding_dimensions,
                    str(request_id),
                )
                count += 1
            except EngineError as error:
                db.rollback()
                if error.code not in {"OUT_OF_SCOPE", "CANCELLED"}:
                    raise
    return count
