"""Conservative relationship resolution, with an injected semantic interpreter.

The interpreter returns a relationship proposal. Scope, conditions, time, and version
checks still run in the write engine; no provider gets direct database access.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from contextbridge.contracts import Candidate, ComparisonContext, WritePlan
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.modules import call_provider

Relation = Literal["same", "correction", "contradiction", "unrelated", "uncertain"]


class RelationInterpreter(Protocol):
    def compare(self, candidate: dict, record: dict) -> Relation: ...


def normalized(content):
    # Deliberately exact: case, identifiers, units, and negation keep their meaning.
    return " ".join(content.split())


@dataclass(frozen=True)
class SafeResolutionPolicy:
    interpreter: RelationInterpreter | None = None

    def resolve(self, candidate: dict, context: dict) -> dict:
        candidate = Candidate.model_validate(candidate)
        context = ComparisonContext.model_validate(context)
        compatible = [
            record
            for record in context.records
            if record.memory.scope == candidate.scope
            and record.memory.project_id == candidate.project_id
            and record.memory.conditions == candidate.conditions
            and record.memory.version.number == record.memory.current_version
            and record.memory.version.status == "ACTIVE"
            and record.memory.version.valid_to is None
        ]

        def plan(operation, record=None, reason="REUSABLE_PROJECT_CONTEXT"):
            return WritePlan(
                schema_version=1,
                candidate_id=candidate.candidate_id,
                operation=operation,
                target_memory_id=record.memory.id if record else None,
                expected_version=record.memory.current_version if record else None,
                reason_codes=[reason],
            ).model_dump(mode="json")

        archived = [
            record
            for record in context.records
            if record.memory.scope == candidate.scope
            and record.memory.project_id == candidate.project_id
            and record.memory.conditions == candidate.conditions
            and record.memory.version.number == record.memory.current_version
            and record.memory.version.status == "SUPERSEDED"
            and record.memory.version.valid_to is not None
        ]
        for record in archived:
            # Imports may refer to a retired fact. Only explicit restoration can reactivate it.
            if normalized(candidate.content) == normalized(record.memory.version.content):
                return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
            if self.interpreter is not None:
                relation = call_provider(
                    lambda record=record: self.interpreter.compare(
                        candidate.model_dump(mode="json"), record.model_dump(mode="json")
                    )
                )
                if relation not in {
                    "same",
                    "correction",
                    "contradiction",
                    "unrelated",
                    "uncertain",
                }:
                    raise ModuleError("INVALID_PROVIDER_OUTPUT")
                if relation != "unrelated":
                    return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
        for record in compatible:
            if normalized(candidate.content) == normalized(record.memory.version.content):
                if record.memory.type != candidate.type:
                    return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
                return plan("NOOP", record, "DUPLICATE")
        if not compatible:
            return plan("CREATE")
        if candidate.claim_key is not None and any(
            record.claim_key == candidate.claim_key and record.memory.type != candidate.type
            for record in compatible
        ):
            # The hosted interpreter currently excludes different categories before comparison.
            # A changed category for the same property must not turn that exclusion into CREATE.
            # Defer classification ambiguity; neither the label nor the key proves equivalence.
            return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
        # Missing optional metadata must not block an unrelated evidenced fact merely
        # because another memory has the same type. The interpreter compares meaning;
        # mutation plans still require a stable property label below and in the engine.
        if self.interpreter is None:
            return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
        relations = []
        for record in compatible:
            relation = call_provider(
                lambda record=record: self.interpreter.compare(
                    candidate.model_dump(mode="json"), record.model_dump(mode="json")
                )
            )
            if not isinstance(relation, str) or relation not in {
                "same",
                "correction",
                "contradiction",
                "unrelated",
                "uncertain",
            }:
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            relations.append((record, relation))
        if any(relation == "uncertain" for _, relation in relations):
            return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
        if any(
            record.memory.type != candidate.type and relation != "unrelated"
            for record, relation in relations
        ):
            # Compare across classifications, but do not guess which classification to keep.
            return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
        same = [record for record, relation in relations if relation == "same"]
        corrections = [record for record, relation in relations if relation == "correction"]
        conflicts = [record for record, relation in relations if relation == "contradiction"]
        if same and not corrections and not conflicts:
            return plan("NOOP", same[0], "DUPLICATE")
        if len(corrections) == 1 and not same and not conflicts:
            if candidate.claim_key is None:
                return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
            record = corrections[0]
            if candidate.valid_from <= record.memory.version.valid_from:
                return plan("DEFER", record, "AMBIGUOUS_TIME")
            return plan("UPDATE", record, "EXPLICIT_DECISION")
        if len(conflicts) == 1 and not corrections and not same:
            if candidate.claim_key is None:
                return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
            return plan("LINK_CONFLICT", conflicts[0], "INSUFFICIENT_EVIDENCE")
        # Contract V1 has one mutation target; multiple conflicts must not be partly marked.
        if not same and not corrections and not conflicts:
            return plan("CREATE")
        return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
