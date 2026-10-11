from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.engine.resolution import SafeResolutionPolicy
from tests.engine.fakes import fixture


def context():
    return {
        "schema_version": 1,
        "checked_at": datetime.now(UTC).isoformat(),
        "records": fixture("retrieval-snapshot")["records"],
    }


class Relation:
    def __init__(self, value):
        self.value = value

    def compare(self, candidate, record):
        return self.value


def test_new_claim_exact_duplicate_and_conditional_coexistence():
    candidate = fixture("candidate")
    ctx = context()
    policy = SafeResolutionPolicy()
    assert policy.resolve(candidate, {**ctx, "records": []})["operation"] == "CREATE"
    assert policy.resolve(candidate, ctx)["operation"] == "NOOP"
    candidate["conditions"] = {"environment": "test"}
    assert policy.resolve(candidate, ctx)["operation"] == "CREATE"


@pytest.mark.parametrize(
    ("relation", "operation"),
    [
        ("same", "NOOP"),
        ("correction", "UPDATE"),
        ("contradiction", "LINK_CONFLICT"),
        ("unrelated", "CREATE"),
        ("uncertain", "DEFER"),
    ],
)
def test_injected_interpretation_proposes_plan_with_version(relation, operation):
    candidate = fixture("candidate")
    candidate["content"] = "Use SQLite instead."
    candidate["valid_from"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    plan = SafeResolutionPolicy(Relation(relation)).resolve(candidate, context())
    assert plan["operation"] == operation
    if operation in {"UPDATE", "LINK_CONFLICT", "NOOP"}:
        assert plan["expected_version"] == 1


def test_claim_label_alone_does_not_establish_correction_or_conflict():
    candidate = fixture("candidate")
    candidate["content"] = "A different primary database."
    assert SafeResolutionPolicy().resolve(candidate, context())["operation"] == "DEFER"


def test_backdated_and_multiple_corrections_defer():
    candidate = fixture("candidate")
    candidate["content"] = "Use SQLite instead."
    candidate["valid_from"] = "2026-10-08T10:00:00Z"
    policy = SafeResolutionPolicy(Relation("correction"))
    assert policy.resolve(candidate, context())["reason_codes"] == ["AMBIGUOUS_TIME"]
    candidate["valid_from"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    ctx = context()
    ctx["records"].append(deepcopy(ctx["records"][0]))
    assert policy.resolve(candidate, ctx)["operation"] == "DEFER"


def test_interpreter_failures_cannot_become_write_plans():
    candidate = fixture("candidate")
    candidate["content"] = "Something different."
    with pytest.raises(ModuleError):
        SafeResolutionPolicy(Relation("accept-latest")).resolve(candidate, context())
