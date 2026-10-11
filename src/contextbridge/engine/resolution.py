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
            and record.memory.type == candidate.type
            and record.memory.version.number == record.memory.current_version
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

        for record in compatible:
            if normalized(candidate.content) == normalized(record.memory.version.content):
                return plan("NOOP", record, "DUPLICATE")
        if not compatible:
            return plan("CREATE")
        if candidate.claim_key is None or self.interpreter is None:
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
        same = [record for record, relation in relations if relation == "same"]
        corrections = [record for record, relation in relations if relation == "correction"]
        conflicts = [record for record, relation in relations if relation == "contradiction"]
        if same and not corrections and not conflicts:
            return plan("NOOP", same[0], "DUPLICATE")
        if len(corrections) == 1 and not same and not conflicts:
            record = corrections[0]
            if candidate.valid_from <= record.memory.version.valid_from:
                return plan("DEFER", record, "AMBIGUOUS_TIME")
            return plan("UPDATE", record, "EXPLICIT_DECISION")
        if conflicts and not corrections and not same:
            return plan("LINK_CONFLICT", conflicts[0], "INSUFFICIENT_EVIDENCE")
        if not same and not corrections and not conflicts:
            return plan("CREATE")
        return plan("DEFER", reason="INSUFFICIENT_EVIDENCE")
