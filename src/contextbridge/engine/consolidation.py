"""Validate and commit injected proposals; never replace the original source facts."""

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import ValidationError
from sqlalchemy import select

from contextbridge.background.outbox import enqueue_work
from contextbridge.contracts import ConsolidationProposal, RetrievalQuery
from contextbridge.contracts.messages import MAX_RECORDS
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.indexing import identity_fingerprint
from contextbridge.engine.modules import call_provider
from contextbridge.models import ConsolidationJob, ConsolidationSource, Memory, MemoryVersion
from contextbridge.persistence.consolidation_cleanup import cancel_consolidation_jobs
from contextbridge.persistence.locks import lock_owner
from contextbridge.persistence.records import record_response
from contextbridge.persistence.relationships import add_derivation
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.schemas import CreateMemory, MemoryType
from contextbridge.security import contains_secret_fields
from contextbridge.service import new_version


def record_fingerprint(memory, version):
    return identity_fingerprint(record_response(memory, version).model_dump(mode="json"))


class ConsolidationService:
    def __init__(self, session, settings, *, commit_guard=None):
        self.session, self.settings = session, settings
        self.commit_guard = commit_guard
        self.repository = PostgresRepository(session, settings.developer_id)

    def enqueue(self, query, version_ids, request_id):
        try:
            query = RetrievalQuery.model_validate(query)
        except (ValidationError, TypeError, ValueError):
            raise EngineError("INVALID_INPUT", 422) from None
        if (
            query.include_developer
            or query.as_of is not None
            or not isinstance(version_ids, list)
            or not 1 <= len(version_ids) <= MAX_RECORDS
            or contains_secret_fields(query.model_dump(mode="json"))
        ):
            raise EngineError("INVALID_INPUT", 422)
        ids = [self.repository.uuid(value) for value in version_ids]
        if len(set(ids)) != len(ids):
            raise EngineError("INVALID_INPUT", 422)
        request_id = self.repository.uuid(request_id)
        fp = identity_fingerprint(
            {
                "scope": query.scope,
                "project": query.project_id,
                "conditions": query.conditions,
                "ids": [str(i) for i in ids],
            }
        )
        lock_owner(self.session, self.settings.developer_id)
        existing = self.session.scalar(
            select(ConsolidationJob).where(
                ConsolidationJob.developer_id == self.settings.developer_id,
                ConsolidationJob.request_id == request_id,
            )
        )
        if existing is not None:
            if existing.status == "cancelled":
                raise EngineError("CANCELLED", 409)
            if existing.request_fingerprint != fp:
                raise EngineError("VERSION_CONFLICT", 409)
            self.session.commit()
            return existing.id
        rows = self.session.execute(
            select(Memory, MemoryVersion)
            .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
            .where(Memory.developer_id == self.settings.developer_id, MemoryVersion.id.in_(ids))
        ).all()
        if len(rows) != len(ids):
            raise EngineError("OUT_OF_SCOPE", 404)
        self.validate_sources(rows, query.scope, query.project_id, query.conditions)
        now = datetime.now(UTC)
        job = ConsolidationJob(
            id=uuid4(),
            developer_id=self.settings.developer_id,
            request_id=request_id,
            request_fingerprint=fp,
            scope=query.scope,
            project_id=query.project_id,
            conditions=query.conditions,
            status="queued",
            reason_codes=[],
            proposals=None,
            result_memory_ids=[],
            expires_at=now + timedelta(seconds=self.settings.candidate_retention_seconds),
            updated_at=now,
        )
        self.session.add(job)
        self.session.flush()
        records = {v.id: (m, v) for m, v in rows}
        for position, version_id in enumerate(ids):
            self.session.add(
                ConsolidationSource(
                    job_id=job.id,
                    version_id=version_id,
                    position=position,
                    source_fingerprint=record_fingerprint(*records[version_id]),
                )
            )
        enqueue_work(
            self.session, "consolidation", job.id, job.developer_id, job.scope, job.project_id
        )
        self.session.commit()
        return job.id

    def locked_job(self, job_id):
        lock_owner(self.session, self.settings.developer_id)
        job = self.session.scalar(
            select(ConsolidationJob)
            .where(
                ConsolidationJob.id == self.repository.uuid(job_id),
                ConsolidationJob.developer_id == self.settings.developer_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if job is None:
            raise EngineError("OUT_OF_SCOPE", 404)
        if self.commit_guard is not None:
            self.commit_guard(self.session)
        if job.expires_at <= datetime.now(UTC) and job.status not in {"succeeded", "cancelled"}:
            cancel_consolidation_jobs(self.session, [job.id])
            self.session.flush()
            self.session.refresh(job)
        return job

    def validate_sources(self, rows, scope, project_id, conditions):
        now = datetime.now(UTC)
        if any(
            m.scope != scope or m.project_id != project_id or m.conditions != conditions
            for m, _ in rows
        ):
            raise ModuleError("OUT_OF_SCOPE")
        if any(
            m.current_version != v.number
            or m.retired_at is not None
            or v.valid_from > now
            or v.valid_to is not None
            or v.status != "ACTIVE"
            or v.decision_state != "clear"
            or not v.evidence
            for m, v in rows
        ):
            raise ModuleError("VERSION_CONFLICT")

    def sources(self, job):
        rows = self.session.execute(
            select(Memory, MemoryVersion, ConsolidationSource)
            .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
            .join(ConsolidationSource, ConsolidationSource.version_id == MemoryVersion.id)
            .where(
                ConsolidationSource.job_id == job.id,
                Memory.developer_id == job.developer_id,
            )
            .order_by(ConsolidationSource.position)
            .limit(MAX_RECORDS + 1)
            .execution_options(populate_existing=True)
        ).all()
        if not 1 <= len(rows) <= MAX_RECORDS:
            raise ModuleError("CANCELLED")
        self.validate_sources(
            [(m, v) for m, v, _ in rows], job.scope, job.project_id, job.conditions
        )
        if any(record_fingerprint(m, v) != source.source_fingerprint for m, v, source in rows):
            raise ModuleError("VERSION_CONFLICT")
        return rows

    def validate_proposals(self, raw, job, rows):
        if not isinstance(raw, list) or len(raw) > 20:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        try:
            proposals = [ConsolidationProposal.model_validate(value) for value in raw]
        except (ValidationError, TypeError, ValueError):
            raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
        if len({p.proposal_id for p in proposals}) != len(proposals):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        records = {v.id: (m, v) for m, v, _ in rows}
        for p in proposals:
            refs = {(r.agent, r.session, r.interaction) for r in p.source_refs}
            expected = {
                (
                    records[i][1].source_agent,
                    records[i][1].source_session,
                    records[i][1].source_interaction,
                )
                for i in p.source_version_ids
                if i in records
            }
            if (
                len(set(p.source_version_ids)) != len(p.source_version_ids)
                or not set(p.source_version_ids) <= records.keys()
                or refs != expected
                or len(refs) != len(p.source_refs)
                or p.scope != job.scope
                or p.project_id != job.project_id
                or p.conditions != job.conditions
                or contains_secret_fields(p.model_dump(mode="json"))
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return proposals

    def inspect(self, job_id):
        job = self.locked_job(job_id)
        result = {
            "job_id": str(job.id),
            "status": job.status,
            "reason_codes": job.reason_codes,
            "retryable": job.retryable,
            "memory_ids": job.result_memory_ids,
        }
        self.session.commit()
        return result

    def process(self, job_id, consolidator):
        try:
            job = self.locked_job(job_id)
            if job.status in {"succeeded", "failed", "cancelled"}:
                self.session.commit()
                return self.inspect(job_id)
            rows = self.sources(job)
            records = [record_response(m, v).model_dump(mode="json") for m, v, _ in rows]
            saved = job.proposals
            job.status, job.updated_at = "running", datetime.now(UTC)
            self.session.commit()
            if saved is None:
                if consolidator is None:
                    raise ModuleError("PROVIDER_UNAVAILABLE")
                raw = call_provider(lambda: consolidator.propose(records))
                job = self.locked_job(job_id)
                if job.status == "cancelled":
                    self.session.commit()
                    return self.inspect(job_id)
                proposals = self.validate_proposals(raw, job, self.sources(job))
                if job.proposals is None:
                    job.proposals = [p.model_dump(mode="json") for p in proposals]
                self.session.commit()
            job = self.locked_job(job_id)
            if job.status in {"succeeded", "cancelled"}:
                self.session.commit()
                return self.inspect(job_id)
            rows = self.sources(job)
            proposals = self.validate_proposals(job.proposals, job, rows)
            versions = {v.id: v for _, v, _ in rows}
            result = []
            for proposal in proposals:
                request_id = uuid5(
                    NAMESPACE_URL, f"contextbridge:consolidation:{proposal.proposal_id}"
                )
                fp = identity_fingerprint(proposal.model_dump(mode="json"))
                memory = self.session.scalar(
                    select(Memory).where(
                        Memory.developer_id == job.developer_id, Memory.request_id == request_id
                    )
                )
                if memory is not None:
                    if memory.request_fingerprint != fp or memory.current_version != 1:
                        raise ModuleError("VERSION_CONFLICT")
                    result.append(str(memory.id))
                    continue
                source = versions[proposal.source_version_ids[0]]
                now = datetime.now(UTC)
                # V1 proposals have no type: derived snapshots use STATE, never rewrite sources.
                payload = CreateMemory(
                    request_id=request_id,
                    scope=job.scope,
                    project_id=job.project_id,
                    type=MemoryType.STATE,
                    content=proposal.summary,
                    conditions=job.conditions,
                    source={
                        "kind": source.source_kind,
                        "agent": source.source_agent,
                        "session": source.source_session,
                        "interaction": source.source_interaction,
                        "evidence": source.evidence,
                    },
                )
                memory = Memory(
                    id=uuid4(),
                    developer_id=job.developer_id,
                    request_id=request_id,
                    request_fingerprint=fp,
                    scope=job.scope,
                    project_id=job.project_id,
                    type=payload.type,
                    conditions=job.conditions,
                    created_at=now,
                    current_version=1,
                )
                self.session.add(memory)
                self.session.flush()
                version = new_version(memory.id, 1, payload, now)
                self.session.add(version)
                self.session.flush()
                for source_id in proposal.source_version_ids:
                    add_derivation(self.session, job.developer_id, version.id, source_id)
                result.append(str(memory.id))
            job.result_memory_ids, job.proposals = result, None
            job.status, job.retryable, job.reason_codes = "succeeded", False, []
            job.updated_at = datetime.now(UTC)
            self.session.commit()
        except ModuleError as error:
            self.session.rollback()
            if isinstance(error, EngineError) and error.code == "OUT_OF_SCOPE":
                raise
            job = self.locked_job(job_id)
            if job.status not in {"succeeded", "cancelled"}:
                job.status = "deferred" if error.retryable else "failed"
                job.retryable, job.reason_codes, job.updated_at = (
                    error.retryable,
                    [error.code],
                    datetime.now(UTC),
                )
                if not error.retryable:
                    job.proposals = None
            self.session.commit()
        return self.inspect(job_id)
