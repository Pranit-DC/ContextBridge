"""Durable candidate execution; providers propose, the shared store commits."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.contracts import (
    AdmissionDecision,
    Candidate,
    CapturedEvent,
    ComparisonContext,
    WritePlan,
)
from contextbridge.contracts.messages import MAX_RECORDS
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.ingestion import IngestionService
from contextbridge.engine.modules import ModuleGateway, call_provider, validate_evidence
from contextbridge.engine.resolution import SafeResolutionPolicy, normalized
from contextbridge.models import (
    CaptureBundle,
    CaptureCandidate,
    CaptureEvent,
    CaptureJob,
    Memory,
    MemoryEdge,
    MemoryVersion,
)
from contextbridge.persistence.capture_cleanup import cancel_capture_jobs
from contextbridge.persistence.records import current_records, record_response
from contextbridge.persistence.relationships import invalidate_derivations
from contextbridge.schemas import CreateMemory
from contextbridge.security import contains_secret_fields
from contextbridge.service import new_version

UNRESOLVED_REASONS = frozenset({"AMBIGUOUS_TIME", "INSUFFICIENT_EVIDENCE"})


def fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class WriteEngine:
    def __init__(
        self, session: Session, settings: Settings, modules: ModuleGateway, *, commit_guard=None
    ):
        self.session = session
        self.settings = settings
        self.modules = modules
        self.ingestion = IngestionService(session, settings)
        self.resolver = modules.resolution or SafeResolutionPolicy()
        self.commit_guard = commit_guard

    def locked_job(self, job_id):
        self.ingestion.require_binding()
        self.ingestion.owner_lock()
        self.ingestion._expire(datetime.now(UTC))
        row = self.session.execute(
            select(CaptureJob, CaptureEvent)
            .join(CaptureEvent, CaptureJob.event_record_id == CaptureEvent.id)
            .where(
                CaptureJob.id == job_id,
                CaptureEvent.developer_id == self.settings.developer_id,
                self.ingestion.scope_filter(),
            )
            .with_for_update()
        ).first()
        if row is None:
            raise EngineError("OUT_OF_SCOPE", 404)
        if self.commit_guard is not None:
            self.commit_guard(self.session)
        return row

    def live_job(self, job_id):
        job, event = self.locked_job(job_id)
        if job.group_leader_id is not None:
            from contextbridge.engine.grouping import members

            group = members(self.ingestion, job, event)
            if any(e.payload is None or j.status == "cancelled" for j, e in group):
                cancel_capture_jobs(self.session, [j.id for j, _ in group])
                self.session.commit()
                raise ModuleError("CANCELLED")
        if event.payload is None or job.status == "cancelled":
            # Expiry/cancellation must survive even when the caller reports an error.
            self.session.commit()
            raise ModuleError("CANCELLED")
        return job, event

    def comparison(self, candidate):
        rows = current_records(
            self.session,
            self.settings.developer_id,
            candidate,
            semantic=self.settings.formation_enabled,
        )
        if len(rows) > MAX_RECORDS:
            raise ModuleError("INVALID_INPUT")
        return ComparisonContext(
            schema_version=1,
            checked_at=datetime.now(UTC),
            records=[record_response(*row) for row in rows],
        )

    def ambiguous_repeat(self, candidate, event):
        """A verbatim sole source cannot establish a novel type/condition without new evidence."""
        if not self.settings.formation_enabled:
            return False
        messages = [message for message in event.messages if message.role != "assistant"]
        if (
            len(messages) != 1
            or len(candidate.evidence_refs) != 1
            or messages[0].content.strip() != candidate.source.evidence.strip()
            or messages[0].role != candidate.source.kind
        ):
            return False
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import JSONB

        return self.session.scalar(
            select(
                select(Memory.id)
                .join(MemoryVersion)
                .where(
                    Memory.developer_id == self.settings.developer_id,
                    Memory.scope == candidate.scope,
                    Memory.project_id == candidate.project_id,
                    MemoryVersion.number == Memory.current_version,
                    Memory.retired_at.is_not(None)
                    | ((MemoryVersion.status == "ACTIVE") & MemoryVersion.valid_to.is_(None)),
                    MemoryVersion.valid_from <= datetime.now(UTC),
                    MemoryVersion.content == candidate.content,
                    MemoryVersion.evidence == candidate.source.evidence,
                    MemoryVersion.source_kind == candidate.source.kind,
                    Memory.retired_at.is_not(None)
                    | (Memory.type != candidate.type)
                    | (cast(Memory.conditions, JSONB) != candidate.conditions),
                )
                .exists()
            )
        )

    def save_extraction(self, job_id, candidates, *, commit=True):
        job, event = self.live_job(job_id)
        if not event.extraction_complete:
            captured = CapturedEvent.model_validate(event.payload)
            from contextbridge.engine.relative_time import review_candidates

            bundled = self.session.get(CaptureBundle, event.id) is not None
            if bundled:
                if not self.settings.capture_evidence_v2_enabled:
                    raise ModuleError("PROVIDER_UNAVAILABLE")
                ambiguous_time = getattr(self.modules.extractor, "needs_confirmation", False)
            else:
                candidates, ambiguous_time = review_candidates(
                    captured, candidates, timezone=self.settings.capture_source_timezone
                )
            for position, candidate in enumerate(candidates):
                validate_evidence(captured, candidate)
                existing = self.session.scalar(
                    select(CaptureCandidate.id).where(
                        CaptureCandidate.developer_id == self.settings.developer_id,
                        CaptureCandidate.candidate_id == candidate.candidate_id,
                    )
                )
                if existing is not None:
                    raise ModuleError("INVALID_PROVIDER_OUTPUT")
                payload = candidate.model_dump(mode="json")
                saved_candidate = CaptureCandidate(
                    id=uuid4(),
                    developer_id=self.settings.developer_id,
                    candidate_id=candidate.candidate_id,
                    position=position,
                    job_id=job.id,
                    payload=payload,
                    fingerprint=fingerprint(payload),
                    expires_at=min(
                        event.expires_at,
                        datetime.now(UTC)
                        + timedelta(seconds=self.settings.candidate_retention_seconds),
                    ),
                    status="pending",
                    reason_codes=[],
                    admission=None,
                    plan=None,
                    comparison_version_ids=[],
                    target_memory_id=None,
                    result_memory_id=None,
                    result_version_id=None,
                )
                self.session.add(saved_candidate)
                if bundled:
                    from contextbridge.evidence_time.storage import save_candidate

                    save_candidate(
                        self.session,
                        self.settings,
                        event,
                        captured,
                        saved_candidate,
                        candidate,
                        self.modules.extractor,
                    )
            event.extraction_complete = True
            if ambiguous_time:
                job.reason_codes = ["AMBIGUOUS_TIME"]
        if commit:
            self.session.commit()

    def candidate_row(self, job_id, candidate_id):
        self.live_job(job_id)
        row = self.session.scalar(
            select(CaptureCandidate)
            .where(
                CaptureCandidate.job_id == job_id,
                CaptureCandidate.candidate_id == candidate_id,
                CaptureCandidate.developer_id == self.settings.developer_id,
            )
            .with_for_update()
        )
        if row is None:
            raise EngineError("OUT_OF_SCOPE", 404)
        return row

    def prepare(self, job_id, candidate_id):
        row = self.candidate_row(job_id, candidate_id)
        if row.status != "pending":
            self.session.commit()
            return
        if row.payload is None:
            raise ModuleError("CANCELLED")
        candidate = Candidate.model_validate(row.payload)
        context = self.comparison(candidate)
        _, event = self.live_job(job_id)
        ambiguous = self.ambiguous_repeat(candidate, CapturedEvent.model_validate(event.payload))
        cached = row.admission is not None and row.plan is not None
        self.session.commit()  # Providers never hold owner or memory row locks.
        if cached:
            return
        admission = (
            AdmissionDecision(
                schema_version=1,
                candidate_id=candidate.candidate_id,
                outcome="DEFER",
                reason_codes=["INSUFFICIENT_EVIDENCE"],
            )
            if ambiguous
            else self.modules.assess(candidate, context)
        )
        if admission.outcome == "ADMIT":
            raw_plan = call_provider(
                lambda: self.resolver.resolve(
                    candidate.model_dump(mode="json"), context.model_dump(mode="json")
                )
            )
            try:
                plan = WritePlan.model_validate(raw_plan)
            except (ValidationError, ValueError, TypeError):
                raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
            if plan.candidate_id != candidate.candidate_id or contains_secret_fields(
                plan.model_dump(mode="json")
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            if plan.target_memory_id is not None and plan.target_memory_id not in {
                record.memory.id for record in context.records
            }:
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            # Pin target identity to the version actually observed, including conflict/no-op plans.
            if plan.target_memory_id is not None and plan.expected_version is None:
                version = next(
                    record.memory.current_version
                    for record in context.records
                    if record.memory.id == plan.target_memory_id
                )
                plan = plan.model_copy(update={"expected_version": version})
        else:
            plan = WritePlan(
                schema_version=1,
                candidate_id=candidate.candidate_id,
                operation="DEFER",
                target_memory_id=None,
                expected_version=None,
                reason_codes=admission.reason_codes,
            )
        row = self.candidate_row(job_id, candidate_id)
        if row.status == "pending" and row.admission is None:
            if (
                plan.target_memory_id is not None
                and self.session.scalar(
                    select(Memory.id).where(
                        Memory.id == plan.target_memory_id,
                        Memory.developer_id == self.settings.developer_id,
                        Memory.scope == candidate.scope,
                        Memory.project_id == candidate.project_id,
                    )
                )
                is None
            ):
                cancel_capture_jobs(self.session, [job_id])
                self.session.commit()
                raise ModuleError("CANCELLED")
            # Concurrent calls race only to save one interpretation. All execution uses the winner.
            row.admission = admission.model_dump(mode="json")
            row.plan = plan.model_dump(mode="json")
            row.target_memory_id = plan.target_memory_id
            row.comparison_version_ids = [
                str(record.memory.version.id)
                for record in context.records
                if record.memory.version.number == record.memory.current_version
                and record.memory.version.status == "ACTIVE"
                and record.memory.version.valid_to is None
                and record.memory.conditions == candidate.conditions
                and (self.settings.formation_enabled or record.memory.type == candidate.type)
            ]
        self.session.commit()

    def defer(self, row, code):
        row.status = "deferred"
        row.reason_codes = [code]

    def execute(self, job_id: UUID, candidate_id: UUID):
        """Execute a saved interpretation at most once, rechecking live data at commit."""
        row = self.candidate_row(job_id, candidate_id)
        if row.status != "pending":
            self.session.commit()
            return
        job, event = self.live_job(job_id)
        candidate = Candidate.model_validate(row.payload)
        validate_evidence(CapturedEvent.model_validate(event.payload), candidate)
        if fingerprint(candidate.model_dump(mode="json")) != row.fingerprint:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        admission = AdmissionDecision.model_validate(row.admission)
        plan = WritePlan.model_validate(row.plan)
        if (
            candidate.candidate_id != admission.candidate_id
            or candidate.candidate_id != plan.candidate_id
        ):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        if admission.outcome == "REJECT":
            from contextbridge.evidence_time.storage import purge_ephemeral

            purge_ephemeral(self.session, candidate_ids=[row.id])
            row.status, row.reason_codes = "rejected", admission.reason_codes
            row.payload = row.fingerprint = None
            row.plan = None
        elif admission.outcome == "DEFER" or plan.operation == "DEFER":
            reasons = admission.reason_codes if admission.outcome == "DEFER" else plan.reason_codes
            self.defer(row, (reasons or ["INSUFFICIENT_EVIDENCE"])[0])
        elif plan.operation == "CREATE" and self.ambiguous_repeat(
            candidate, CapturedEvent.model_validate(event.payload)
        ):
            self.defer(row, "INSUFFICIENT_EVIDENCE")
        else:
            self.apply_plan(row, candidate, plan)
        job.updated_at = datetime.now(UTC)
        self.session.commit()

    def apply_plan(self, row, candidate, plan):
        now = datetime.now(UTC)
        rows = current_records(
            self.session,
            self.settings.developer_id,
            candidate,
            semantic=self.settings.formation_enabled,
        )
        if len(rows) > MAX_RECORDS:
            self.defer(row, "INSUFFICIENT_EVIDENCE")
            return
        compatible = [
            (memory, version)
            for memory, version in rows
            if memory.conditions == candidate.conditions
            and (self.settings.formation_enabled or memory.type == candidate.type)
            and memory.current_version == version.number
            and memory.retired_at is None
        ]
        duplicate = next(
            (
                (memory, version)
                for memory, version in compatible
                if normalized(version.content) == normalized(candidate.content)
            ),
            None,
        )
        target = previous = None
        if plan.target_memory_id is not None:
            target = self.session.scalar(
                select(Memory)
                .where(
                    Memory.id == plan.target_memory_id,
                    Memory.developer_id == self.settings.developer_id,
                    Memory.scope == candidate.scope,
                    Memory.project_id == candidate.project_id,
                )
                .with_for_update()
            )
            if target is None:
                self.defer(row, "CANCELLED")
                return
            if target.retired_at is not None:
                self.defer(row, "CANCELLED")
                return
            if target.conditions != candidate.conditions or target.type != candidate.type:
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            if plan.expected_version != target.current_version:
                self.defer(row, "VERSION_CONFLICT")
                return
            previous = self.session.scalar(
                select(MemoryVersion)
                .where(
                    MemoryVersion.memory_id == target.id,
                    MemoryVersion.number == target.current_version,
                )
                .with_for_update()
            )
            exact_noop = plan.operation == "NOOP" and normalized(candidate.content) == normalized(
                previous.content
            )
            compared_target = str(previous.id) in row.comparison_version_ids
            if (
                target.claim_key != candidate.claim_key
                and not exact_noop
                and not (self.settings.formation_enabled and compared_target)
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
        if duplicate is not None and plan.operation in {"CREATE", "NOOP"}:
            target, previous = duplicate
            row.result_memory_id, row.result_version_id = target.id, previous.id
            row.status, row.reason_codes = "applied", ["DUPLICATE"]
            return
        if plan.operation == "NOOP":
            if target is None:
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            row.result_memory_id, row.result_version_id = target.id, previous.id
            row.status, row.reason_codes = "applied", plan.reason_codes
            return
        if plan.operation in {"CREATE", "UPDATE", "LINK_CONFLICT"} and {
            str(version.id) for _, version in compatible
        } != set(row.comparison_version_ids):
            # Related state changed since the proposal; do not reinterpret the stored plan.
            self.defer(row, "VERSION_CONFLICT")
            return
        if plan.operation in {"UPDATE", "LINK_CONFLICT"} and (
            target is None or candidate.claim_key is None
        ):
            self.defer(row, "INSUFFICIENT_EVIDENCE")
            return
        if plan.operation == "UPDATE":
            if "EXPLICIT_DECISION" not in plan.reason_codes:
                self.defer(row, "INSUFFICIENT_EVIDENCE")
                return
            if candidate.valid_from <= previous.valid_from:
                self.defer(row, "AMBIGUOUS_TIME")
                return
            from contextbridge.evidence_time.storage import transition_start
            from contextbridge.evidence_time.temporal import TemporalAmbiguity

            try:
                effective_start = transition_start(self.session, row, candidate, previous)
            except TemporalAmbiguity:
                self.defer(row, "AMBIGUOUS_TIME")
                return
            invalidate_derivations(
                self.session,
                self.settings.developer_id,
                target,
                effective_start,
                exclude_job_id=row.job_id,
            )
            previous.status, previous.valid_to = "SUPERSEDED", effective_start
            target.current_version += 1
            version = new_version(target.id, target.current_version, candidate, now)
            version.confidence, version.decision_state = (
                candidate.confidence,
                previous.decision_state,
            )
            self.session.add(version)
            self.session.flush()
            self.session.add(
                MemoryEdge(
                    id=uuid4(),
                    from_version_id=version.id,
                    to_version_id=previous.id,
                    relation="supersedes",
                )
            )
        else:
            request_id = uuid5(NAMESPACE_URL, f"contextbridge:candidate:{candidate.candidate_id}")
            if self.session.scalar(
                select(Memory.id).where(
                    Memory.developer_id == self.settings.developer_id,
                    Memory.request_id == request_id,
                )
            ):
                raise ModuleError("VERSION_CONFLICT")
            payload = CreateMemory(
                request_id=request_id,
                scope=candidate.scope,
                project_id=candidate.project_id,
                type=candidate.type,
                conditions=candidate.conditions,
                content=candidate.content,
                source=candidate.source,
                valid_from=candidate.valid_from,
            )
            created = Memory(
                id=uuid4(),
                developer_id=self.settings.developer_id,
                request_id=request_id,
                request_fingerprint=fingerprint(payload.model_dump(mode="json")),
                scope=candidate.scope.value,
                project_id=candidate.project_id,
                type=candidate.type.value,
                conditions=candidate.conditions,
                created_at=now,
                current_version=1,
                claim_key=candidate.claim_key,
            )
            self.session.add(created)
            self.session.flush()
            version = new_version(created.id, 1, candidate, now)
            version.confidence = candidate.confidence
            version.decision_state = "contested" if plan.operation == "LINK_CONFLICT" else "clear"
            self.session.add(version)
            self.session.flush()
            if plan.operation == "LINK_CONFLICT":
                invalidate_derivations(
                    self.session, self.settings.developer_id, target, now, exclude_job_id=row.job_id
                )
                previous.decision_state = "contested"
                self.session.add(
                    MemoryEdge(
                        id=uuid4(),
                        from_version_id=version.id,
                        to_version_id=previous.id,
                        relation="contradicts",
                    )
                )
            target = created
        from contextbridge.evidence_time.storage import applied

        applied(
            self.session,
            self.settings,
            row,
            candidate,
            version,
            previous if plan.operation == "UPDATE" else None,
        )
        from contextbridge.persistence.related import link_related

        link_related(self.session, self.settings.developer_id, version.id)
        row.result_memory_id, row.result_version_id = target.id, version.id
        row.status, row.reason_codes = "applied", plan.reason_codes

    def process(self, job_id: UUID):
        from contextbridge.engine.grouping import aggregate, distribute, members

        job, event = self.locked_job(job_id)
        if (
            event.payload is None
            or job.status == "cancelled"
            or (
                job.group_leader_id is None
                and job.status not in {"queued", "running"}
                and not job.retryable
            )
        ):
            self.session.commit()
            return self.ingestion.inspect_job(job_id)
        if (
            self.session.get(CaptureBundle, event.id) is not None
            and not self.settings.capture_evidence_v2_enabled
        ):
            self.session.commit()
            return self.ingestion.inspect_job(job_id)
        group = members(self.ingestion, job, event)
        if group is None or group[0][0].id != job_id:
            self.session.commit()
            return self.ingestion.inspect_job(job_id)
        if len(group) == 1:
            self.session.commit()
            return self._process_one(job_id)
        ids = [j.id for j, _ in group]
        complete = all(e.extraction_complete for _, e in group)
        if not complete:
            captured, mapping = aggregate(group)
            self.session.commit()
            try:
                candidates = self.modules.extract(captured)
                distributed, deferred = distribute(candidates, mapping, group)
                # One transaction saves every event's interpretation, or none of them.
                for identifier in ids:
                    self.save_extraction(identifier, distributed[identifier], commit=False)
                    if identifier in deferred or (
                        not candidates
                        and getattr(self.modules.extractor, "needs_confirmation", False) is True
                    ):
                        member, _ = self.live_job(identifier)
                        member.reason_codes = sorted(
                            set(member.reason_codes) | {"INSUFFICIENT_EVIDENCE"}
                        )
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        for identifier in ids:
            self._process_one(identifier)
        return self.ingestion.inspect_job(job_id)

    def _process_one(self, job_id: UUID):
        try:
            job, event = self.live_job(job_id)
            if job.status in {"succeeded", "failed"} or (
                job.status == "deferred" and not job.retryable
            ):
                self.session.commit()
                return self.ingestion.inspect_job(job_id)
            complete = event.extraction_complete
            captured = CapturedEvent.model_validate(event.payload)
            job.status, job.retryable, job.updated_at = "running", False, datetime.now(UTC)
            self.session.commit()
            if not complete:
                candidates = self.modules.extract(captured)
                self.save_extraction(job_id, candidates)
                if (
                    not candidates
                    and getattr(self.modules.extractor, "needs_confirmation", False) is True
                ):
                    job, _ = self.live_job(job_id)
                    job.status, job.retryable = "deferred", False
                    job.reason_codes = ["INSUFFICIENT_EVIDENCE"]
                    self.session.commit()
                    return self.ingestion.inspect_job(job_id)
            ids = self.session.scalars(
                select(CaptureCandidate.candidate_id)
                .where(CaptureCandidate.job_id == job_id)
                .order_by(CaptureCandidate.position)
            ).all()
            self.session.commit()
            for candidate_id in ids:
                self.prepare(job_id, candidate_id)
                self.execute(job_id, candidate_id)
            job, _ = self.live_job(job_id)
            outcomes = self.session.scalars(
                select(CaptureCandidate.status).where(CaptureCandidate.job_id == job_id)
            ).all()
            unresolved = set(job.reason_codes) & UNRESOLVED_REASONS
            job.status = "deferred" if "deferred" in outcomes or unresolved else "succeeded"
            job.retryable = False
            reasons = self.session.scalars(
                select(CaptureCandidate.reason_codes).where(CaptureCandidate.job_id == job_id)
            ).all()
            job.reason_codes = sorted(
                unresolved | {reason for group in reasons for reason in group}
            )[:20]
            job.updated_at = datetime.now(UTC)
            self.session.commit()
        except (ModuleError, ValidationError) as error:
            self.session.rollback()
            if isinstance(error, EngineError) and error.code == "OUT_OF_SCOPE":
                raise
            code = error.code if isinstance(error, ModuleError) else "INVALID_PROVIDER_OUTPUT"
            retryable = error.retryable if isinstance(error, ModuleError) else False
            job, _ = self.locked_job(job_id)
            if job.status not in {"cancelled", "succeeded"}:
                reasons = sorted((set(job.reason_codes) & UNRESOLVED_REASONS) | {code})
                job.status = "deferred" if retryable else "failed"
                job.retryable, job.reason_codes, job.updated_at = (
                    retryable,
                    reasons,
                    datetime.now(UTC),
                )
            self.session.commit()
        return self.ingestion.inspect_job(job_id)
