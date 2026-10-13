"""Durable ingestion only. Accepted jobs await the separately integrated processor."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from contextbridge.background.outbox import enqueue_work
from contextbridge.config import Settings
from contextbridge.contracts import CapturedEvent, IngestionResponse, JobResponse
from contextbridge.engine.errors import IngestionError
from contextbridge.models import CaptureCandidate, CaptureEvent, CaptureJob, Memory
from contextbridge.persistence.capture_cleanup import expire_candidates
from contextbridge.persistence.locks import lock_owner
from contextbridge.schemas import Scope
from contextbridge.security import contains_secret_fields


class IngestionService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings

    def require_binding(self):
        if self.settings.capture_project_id is None:
            raise IngestionError("PROVIDER_UNAVAILABLE", 503)

    def recent_jobs(self, project_id):
        self.require_binding()
        if project_id != self.settings.capture_project_id:
            raise IngestionError("OUT_OF_SCOPE", 404)
        ids = self.session.scalars(
            select(CaptureJob.id)
            .join(CaptureEvent, CaptureJob.event_record_id == CaptureEvent.id)
            .where(
                CaptureEvent.developer_id == self.settings.developer_id,
                CaptureEvent.scope == "project",
                CaptureEvent.project_id == project_id,
            )
            .order_by(CaptureJob.updated_at.desc(), CaptureJob.id)
            .limit(20)
        ).all()
        return [self.inspect_job(identifier) for identifier in ids]

    def scope_filter(self):
        project = (CaptureEvent.scope == "project") & (
            CaptureEvent.project_id == self.settings.capture_project_id
        )
        if self.settings.capture_allow_developer:
            return or_(project, CaptureEvent.scope == "developer")
        return project

    def owner_lock(self):
        # Serialize quota and event replay decisions across processes and project bindings.
        # Transaction-scoped locks release on commit, rollback, or connection loss.
        lock_owner(self.session, self.settings.developer_id)

    def _expire(self, now: datetime) -> int:
        # Clear in SQL without loading every expired transcript into process memory.
        ids = self.session.scalars(
            update(CaptureEvent)
            .where(
                CaptureEvent.developer_id == self.settings.developer_id,
                self.scope_filter(),
                CaptureEvent.expires_at <= now,
                CaptureEvent.payload.is_not(None),
            )
            .values(payload=None, fingerprint=None)
            .returning(CaptureEvent.id)
            .execution_options(synchronize_session=False)
        ).all()
        # Bound SQL parameters even at the maximum configured buffer capacity.
        for offset in range(0, len(ids), 500):
            self.session.execute(
                update(CaptureJob)
                .where(
                    CaptureJob.event_record_id.in_(ids[offset : offset + 500]),
                    CaptureJob.status.in_(["queued", "running", "deferred"]),
                )
                .values(status="cancelled", reason_codes=["CANCELLED"], updated_at=now)
                .execution_options(synchronize_session=False)
            )
            job_ids = select(CaptureJob.id).where(
                CaptureJob.event_record_id.in_(ids[offset : offset + 500])
            )
            self.session.execute(
                update(CaptureCandidate)
                .where(CaptureCandidate.job_id.in_(job_ids))
                .values(
                    payload=None,
                    fingerprint=None,
                    admission=None,
                    plan=None,
                )
                .execution_options(synchronize_session=False)
            )
            self.session.execute(
                update(CaptureCandidate)
                .where(
                    CaptureCandidate.job_id.in_(job_ids),
                    CaptureCandidate.status.in_(["pending", "deferred"]),
                )
                .values(status="cancelled", reason_codes=["CANCELLED"])
                .execution_options(synchronize_session=False)
            )
        expire_candidates(self.session, self.settings.developer_id, self.scope_filter(), now)
        # Bulk cleanup must invalidate ORM objects held by a long-lived engine session.
        self.session.expire_all()
        return len(ids)

    def expire(self) -> int:
        self.require_binding()
        self.owner_lock()
        count = self._expire(datetime.now(UTC))
        self.session.commit()
        return count

    def ingest(self, event: CapturedEvent) -> IngestionResponse:
        self.require_binding()
        if (
            event.scope == Scope.PROJECT and event.project_id != self.settings.capture_project_id
        ) or (event.scope == Scope.DEVELOPER and not self.settings.capture_allow_developer):
            raise IngestionError("OUT_OF_SCOPE", 404)
        payload = event.model_dump(mode="json")
        if event.capture_method != "manual_import" or contains_secret_fields(payload):
            raise IngestionError("INVALID_INPUT", 422)
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.owner_lock()
        now = datetime.now(UTC)
        self._expire(now)
        existing = self.session.scalar(
            select(CaptureEvent).where(
                CaptureEvent.developer_id == self.settings.developer_id,
                CaptureEvent.event_id == event.event_id,
            )
        )
        if existing is not None:
            # Commit expiry even when this request ends in a replay/cancellation error.
            self.session.commit()
            if existing.scope != event.scope.value or existing.project_id != event.project_id:
                raise IngestionError("OUT_OF_SCOPE", 404)
            if existing.payload is None:
                raise IngestionError("CANCELLED", 409)
            if existing.fingerprint != fingerprint:
                raise IngestionError("VERSION_CONFLICT", 409)
            job = self.session.scalar(
                select(CaptureJob).where(CaptureJob.event_record_id == existing.id)
            )
            return IngestionResponse(
                schema_version=1, event_id=event.event_id, job_id=job.id, status="duplicate"
            )
        count = self.session.scalar(
            select(func.count())
            .select_from(CaptureEvent)
            .where(
                CaptureEvent.developer_id == self.settings.developer_id,
                CaptureEvent.payload.is_not(None),
            )
        )
        if count >= self.settings.capture_max_buffered_events:
            self.session.commit()
            raise IngestionError("STORAGE_UNAVAILABLE", 503, retryable=True)
        saved = CaptureEvent(
            id=uuid4(),
            developer_id=self.settings.developer_id,
            event_id=event.event_id,
            scope=event.scope.value,
            project_id=event.project_id,
            payload=payload,
            fingerprint=fingerprint,
            received_at=now,
            expires_at=now + timedelta(seconds=self.settings.capture_retention_seconds),
        )
        job = CaptureJob(
            id=uuid4(),
            event_record_id=saved.id,
            status="queued",
            reason_codes=[],
            updated_at=now,
        )
        self.session.add(saved)
        self.session.flush()
        self.session.add(job)
        enqueue_work(
            self.session, "capture", job.id, saved.developer_id, saved.scope, saved.project_id
        )
        self.session.commit()
        return IngestionResponse(
            schema_version=1, event_id=event.event_id, job_id=job.id, status="accepted"
        )

    def inspect_job(self, job_id: UUID) -> JobResponse:
        self.require_binding()
        self.owner_lock()
        self._expire(datetime.now(UTC))
        row = self.session.execute(
            select(CaptureJob, CaptureEvent.event_id)
            .join(CaptureEvent, CaptureJob.event_record_id == CaptureEvent.id)
            .where(
                CaptureJob.id == job_id,
                CaptureEvent.developer_id == self.settings.developer_id,
                self.scope_filter(),
            )
        ).first()
        self.session.commit()
        if row is None:
            raise IngestionError("OUT_OF_SCOPE", 404)
        job, event_id = row
        memory_ids = self.session.scalars(
            select(Memory.id)
            .join(CaptureCandidate, CaptureCandidate.result_memory_id == Memory.id)
            .join(CaptureJob, CaptureCandidate.job_id == CaptureJob.id)
            .join(CaptureEvent, CaptureJob.event_record_id == CaptureEvent.id)
            .where(
                CaptureCandidate.job_id == job.id,
                CaptureCandidate.status == "applied",
                Memory.developer_id == self.settings.developer_id,
                CaptureCandidate.developer_id == self.settings.developer_id,
                Memory.scope == CaptureEvent.scope,
                Memory.project_id.is_not_distinct_from(CaptureEvent.project_id),
            )
            .distinct()
            .order_by(Memory.id)
        ).all()
        return JobResponse(
            schema_version=1,
            job_id=job.id,
            event_id=event_id,
            status=job.status,
            reason_codes=job.reason_codes,
            memory_ids=memory_ids,
            updated_at=job.updated_at,
        )
