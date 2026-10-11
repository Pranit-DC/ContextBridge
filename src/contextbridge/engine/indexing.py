"""Durable, bounded reindex batches. Providers never own a store or hold write locks."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from contextbridge.background.outbox import enqueue_work
from contextbridge.contracts import EmbeddingBatch, RetrievalQuery
from contextbridge.contracts.messages import MAX_RECORDS
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.modules import call_provider
from contextbridge.models import (
    EmbeddingModel,
    Memory,
    MemoryEmbedding,
    MemoryVersion,
    ReindexJob,
    ReindexTarget,
)
from contextbridge.persistence.locks import lock_owner
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.persistence.vectors import content_fingerprint, vector32
from contextbridge.security import contains_secret_fields


def identity_fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_fingerprint(memory, version):
    return identity_fingerprint(
        {
            "content": version.content,
            "conditions": memory.conditions,
            "owner": memory.developer_id,
            "scope": memory.scope,
            "project": memory.project_id,
            "type": memory.type,
        }
    )


class IndexService:
    def __init__(self, session, developer_id, *, commit_guard=None):
        self.session, self.developer_id = session, developer_id
        self.repository = PostgresRepository(session, developer_id)
        self.commit_guard = commit_guard

    def enqueue(self, query, version_ids, model_id, dimensions, request_id):
        try:
            original = RetrievalQuery.model_validate(query)
            model = EmbeddingBatch.model_validate(
                {"model_id": model_id, "dimensions": dimensions, "vectors": []}
            )
        except (ValidationError, TypeError, ValueError):
            raise EngineError("INVALID_INPUT", 422) from None
        model_id, dimensions = model.model_id, model.dimensions
        query = self.repository.query(query)
        if (
            original.include_developer
            or not isinstance(version_ids, list)
            or not 1 <= len(version_ids) <= MAX_RECORDS
        ):
            raise EngineError("INVALID_INPUT", 422)
        ids = [self.repository.uuid(value) for value in version_ids]
        if len(set(ids)) != len(ids) or contains_secret_fields(model.model_dump(mode="json")):
            raise EngineError("INVALID_INPUT", 422)
        request_id = self.repository.uuid(request_id)
        fingerprint = identity_fingerprint(
            {
                "filter": original.model_dump(mode="json", exclude={"query", "limit"}),
                "ids": [str(value) for value in ids],
                "model": model_id,
                "dimensions": dimensions,
            }
        )
        lock_owner(self.session, self.developer_id)
        existing = self.session.scalar(
            select(ReindexJob).where(
                ReindexJob.developer_id == self.developer_id, ReindexJob.request_id == request_id
            )
        )
        if existing is not None:
            if existing.status == "cancelled":
                raise EngineError("CANCELLED", 409)
            if existing.request_fingerprint != fingerprint:
                raise EngineError("VERSION_CONFLICT", 409)
            self.session.commit()
            return existing.id
        registry = self.session.get(EmbeddingModel, (self.developer_id, model_id))
        if registry is not None and registry.dimensions != dimensions:
            raise EngineError("INVALID_INPUT", 422)
        if registry is None:
            self.session.add(
                EmbeddingModel(
                    developer_id=self.developer_id, model_id=model_id, dimensions=dimensions
                )
            )
            self.session.flush()
        rows = {
            version.id: (memory, version)
            for memory, version in self.session.execute(
                self.repository.eligible(query).where(MemoryVersion.id.in_(ids))
            )
        }
        if set(rows) != set(ids):
            raise EngineError("OUT_OF_SCOPE", 404)
        job = ReindexJob(
            id=uuid4(),
            developer_id=self.developer_id,
            request_id=request_id,
            request_fingerprint=fingerprint,
            scope=query.scope,
            project_id=query.project_id,
            model_id=model_id,
            dimensions=dimensions,
            as_of=query.as_of,
            status="queued",
            reason_codes=[],
            updated_at=datetime.now(UTC),
        )
        self.session.add(job)
        self.session.flush()
        for position, version_id in enumerate(ids):
            self.session.add(
                ReindexTarget(
                    job_id=job.id,
                    version_id=version_id,
                    position=position,
                    source_fingerprint=source_fingerprint(*rows[version_id]),
                )
            )
        enqueue_work(self.session, "reindex", job.id, job.developer_id, job.scope, job.project_id)
        self.session.commit()
        return job.id

    def locked_job(self, job_id):
        lock_owner(self.session, self.developer_id)
        self.session.expire_all()
        job = self.session.scalar(
            select(ReindexJob)
            .where(
                ReindexJob.id == self.repository.uuid(job_id),
                ReindexJob.developer_id == self.developer_id,
            )
            .with_for_update()
        )
        if job is None:
            raise EngineError("OUT_OF_SCOPE", 404)
        if self.commit_guard is not None:
            self.commit_guard(self.session)
        return job

    def rows(self, job):
        targets = self.session.scalars(
            select(ReindexTarget)
            .where(ReindexTarget.job_id == job.id)
            .order_by(ReindexTarget.position)
            .limit(MAX_RECORDS + 1)
        ).all()
        if not 1 <= len(targets) <= MAX_RECORDS:
            raise ModuleError("CANCELLED")
        rows = self.session.execute(
            select(Memory, MemoryVersion, ReindexTarget)
            .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
            .join(ReindexTarget, ReindexTarget.version_id == MemoryVersion.id)
            .where(
                ReindexTarget.job_id == job.id,
                Memory.developer_id == self.developer_id,
                Memory.scope == job.scope,
                Memory.project_id == job.project_id,
                MemoryVersion.valid_from <= job.as_of,
                (MemoryVersion.valid_to.is_(None) | (MemoryVersion.valid_to > job.as_of)),
            )
            .order_by(ReindexTarget.position)
            .execution_options(populate_existing=True)
        ).all()
        if len(rows) != len(targets) or any(
            source_fingerprint(memory, version) != target.source_fingerprint
            for memory, version, target in rows
        ):
            raise ModuleError("CANCELLED")
        return rows

    def inspect(self, job_id):
        job = self.locked_job(job_id)
        result = {
            "job_id": str(job.id),
            "status": job.status,
            "reason_codes": job.reason_codes,
            "model_id": job.model_id,
            "dimensions": job.dimensions,
            "retryable": job.retryable,
        }
        self.session.commit()
        return result

    def process(self, job_id, embedder):
        try:
            job = self.locked_job(job_id)
            if job.status in {"succeeded", "failed", "cancelled"} or (
                job.status == "deferred" and not job.retryable
            ):
                self.session.commit()
                return self.inspect(job_id)
            rows = self.rows(job)
            ids = [version.id for _, version, _ in rows]
            texts = [version.content for _, version, _ in rows]
            model_id, dimensions = job.model_id, job.dimensions
            job.status, job.retryable, job.updated_at = "running", False, datetime.now(UTC)
            self.session.commit()
            if contains_secret_fields(texts):
                raise ModuleError("INVALID_INPUT")
            if embedder is None:
                raise ModuleError("EMBEDDING_UNAVAILABLE")
            raw = call_provider(lambda: embedder.embed(texts))
            batch = EmbeddingBatch.model_validate(raw)
            if (
                batch.model_id != model_id
                or batch.dimensions != dimensions
                or len(batch.vectors) != len(texts)
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            vectors = [vector32(vector, code="INVALID_PROVIDER_OUTPUT") for vector in batch.vectors]
            job = self.locked_job(job_id)
            if job.status in {"cancelled", "succeeded"}:
                self.session.commit()
                return self.inspect(job_id)
            rows = self.rows(job)
            if [version.id for _, version, _ in rows] != ids:
                raise ModuleError("CANCELLED")
            for (_, version, _), vector in zip(rows, vectors, strict=True):
                values = dict(
                    version_id=version.id,
                    developer_id=self.developer_id,
                    model_id=model_id,
                    dimensions=dimensions,
                    vector=vector,
                    content_fingerprint=content_fingerprint(version.content),
                    indexed_at=datetime.now(UTC),
                )
                self.session.execute(
                    insert(MemoryEmbedding)
                    .values(**values)
                    .on_conflict_do_update(
                        index_elements=[MemoryEmbedding.version_id, MemoryEmbedding.model_id],
                        set_={
                            key: value
                            for key, value in values.items()
                            if key not in {"version_id", "model_id"}
                        },
                    )
                )
            job.status, job.retryable, job.reason_codes, job.updated_at = (
                "succeeded",
                False,
                [],
                datetime.now(UTC),
            )
            self.session.commit()
        except (ModuleError, ValidationError) as error:
            self.session.rollback()
            if isinstance(error, EngineError) and error.code == "OUT_OF_SCOPE":
                raise
            code = error.code if isinstance(error, ModuleError) else "INVALID_PROVIDER_OUTPUT"
            retryable = error.retryable if isinstance(error, ModuleError) else False
            job = self.locked_job(job_id)
            if job.status not in {"cancelled", "succeeded"}:
                job.status = (
                    "cancelled" if code == "CANCELLED" else "deferred" if retryable else "failed"
                )
                job.retryable, job.reason_codes, job.updated_at = (
                    retryable,
                    [code],
                    datetime.now(UTC),
                )
                if job.status == "cancelled":
                    job.request_fingerprint = None
            self.session.commit()
        return self.inspect(job_id)
