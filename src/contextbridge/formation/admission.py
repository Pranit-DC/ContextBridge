"""Initial evidence gate and exact scoped comparison; no conflict interpretation or writes."""

from collections.abc import Callable
from datetime import UTC, datetime
from math import isfinite

from contextbridge.contracts import AdmissionDecision, Candidate, ComparisonContext
from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers import EvidenceVerifier, call, check_support
from contextbridge.formation.validation import has_provenance, screened_event, validate
from contextbridge.security import contains_secret_fields


class AdmissionPolicy:
    def __init__(
        self,
        verifier: EvidenceVerifier,
        event_lookup: Callable[[str], dict | None],
        *,
        min_confidence: float = 0.8,
        min_usefulness: float = 0.6,
    ):
        for value in (min_confidence, min_usefulness):
            if isinstance(value, bool) or not isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Thresholds must be finite numbers from zero to one")
        self.verifier = verifier
        self.event_lookup = event_lookup
        self.min_confidence = min_confidence
        self.min_usefulness = min_usefulness

    def assess(self, candidate: dict, context: dict) -> dict:
        proposed = validate(Candidate, candidate)
        compared = validate(ComparisonContext, context)

        def decision(outcome, *reasons):
            return AdmissionDecision(
                schema_version=1,
                candidate_id=proposed.candidate_id,
                outcome=outcome,
                reason_codes=list(reasons),
            ).model_dump(mode="json")

        if contains_secret_fields(candidate) or contains_secret_fields(
            proposed.model_dump(mode="json")
        ):
            return decision("REJECT", "SECRET_DETECTED")
        if contains_secret_fields(context) or contains_secret_fields(
            compared.model_dump(mode="json")
        ):
            raise ModuleError("INVALID_INPUT")
        if proposed.valid_from > compared.checked_at or compared.checked_at > datetime.now(UTC):
            return decision("DEFER", "AMBIGUOUS_TIME")
        try:
            raw_event = call(lambda: self.event_lookup(str(proposed.event_id)))
            if raw_event is None:
                return decision("DEFER", "INSUFFICIENT_EVIDENCE")
            event = screened_event(raw_event)
            if not has_provenance(proposed, event):
                return decision("REJECT", "UNSUPPORTED_CLAIM")
            support = check_support(
                self.verifier, proposed.model_dump(mode="json"), event.model_dump(mode="json")
            )
        except ModuleError as exc:
            if exc.code == "PROVIDER_UNAVAILABLE":
                return decision("DEFER", "PROVIDER_UNAVAILABLE")
            raise
        if support == "unsupported":
            return decision("REJECT", "UNSUPPORTED_CLAIM")
        if support == "uncertain" or proposed.confidence < self.min_confidence:
            return decision("DEFER", "INSUFFICIENT_EVIDENCE")
        if proposed.usefulness < self.min_usefulness:
            return decision("REJECT", "LOW_USEFULNESS")
        for record in compared.records:
            memory = record.memory
            version = memory.version
            if (
                memory.scope == proposed.scope
                and memory.project_id == proposed.project_id
                and memory.type == proposed.type
                and memory.conditions == proposed.conditions
                and record.decision_state == "clear"
                and version.number == memory.current_version
                and version.status == "ACTIVE"
                and version.valid_from <= proposed.valid_from
                and (version.valid_to is None or proposed.valid_from < version.valid_to)
                and version.content == proposed.content
            ):
                return decision("REJECT", "DUPLICATE")
        reasons = ["REUSABLE_PROJECT_CONTEXT"]
        if proposed.type == "DECISION" and proposed.source.kind == "user":
            reasons.insert(0, "EXPLICIT_DECISION")
        return decision("ADMIT", *reasons)
