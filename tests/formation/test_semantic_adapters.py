"""Injected semantic fixtures validate safeguards, not actual model accuracy."""

import copy
import json
from types import SimpleNamespace

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Consolidator
from contextbridge.formation.providers.conventions import normalize_conditions
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier
from contextbridge.formation.providers.semantic import (
    ChatConsolidationVerifier,
    ChatDuplicateVerifier,
    ChatGroupingProvider,
)
from scripts.formation.demo_consolidation import load_cases


def client(responses):
    sent = []
    values = iter(responses)

    def complete(model, prompt, payload, schema):
        sent.append(copy.deepcopy(payload))
        return json.dumps(next(values))

    return SimpleNamespace(
        settings=SimpleNamespace(model="synthetic", verifier_model="synthetic"), complete=complete
    ), sent


def comparable(candidate, record):
    record = copy.deepcopy(record)
    memory = record["memory"]
    memory.update(
        scope=candidate["scope"],
        project_id=candidate["project_id"],
        type=candidate["type"],
        conditions=candidate["conditions"],
    )
    memory["version"]["content"] = "Paraphrased existing decision with the same value."
    return record


@pytest.mark.parametrize(
    "relation,outcome,reason",
    [
        ("equivalent", "REJECT", "DUPLICATE"),
        ("uncertain", "DEFER", "INSUFFICIENT_EVIDENCE"),
        ("different", "ADMIT", "EXPLICIT_DECISION"),
    ],
)
def test_bounded_semantic_comparison_is_opt_in_and_never_mutates(
    relation,
    outcome,
    reason,
    event,
    candidate,
    record,
    context,
):
    snapshot = context | {"records": [comparable(candidate, record)]}
    original = copy.deepcopy(snapshot)
    evidence = RecordedEvidenceVerifier([(event, candidate, "supported")])
    fake, sent = client([{"relation": relation}])
    policy = AdmissionPolicy(
        evidence, lambda _: event, duplicate_verifier=ChatDuplicateVerifier(fake)
    )
    result = policy.assess(candidate, snapshot)
    assert result["outcome"] == outcome and reason in result["reason_codes"]
    assert len(sent) == 1 and snapshot == original
    assert (
        AdmissionPolicy(evidence, lambda _: event).assess(candidate, snapshot)["outcome"] == "ADMIT"
    )


@pytest.mark.parametrize("fault", ["project", "conditions", "contested", "stale", "future", "type"])
def test_ineligible_comparison_records_never_reach_model(fault, event, candidate, record, context):
    record = comparable(candidate, record)
    memory = record["memory"]
    if fault == "project":
        memory["project_id"] = "other-project"
    elif fault == "conditions":
        memory["conditions"] = {"environment": "other"}
    elif fault == "contested":
        record["decision_state"] = "contested"
    elif fault == "stale":
        memory["current_version"] += 1
    elif fault == "future":
        memory["created_at"] = "2099-01-01T00:00:00Z"
    else:
        memory["type"] = "FACT" if candidate["type"] != "FACT" else "STATE"
    fake, sent = client([])
    policy = AdmissionPolicy(
        RecordedEvidenceVerifier([(event, candidate, "supported")]),
        lambda _: event,
        duplicate_verifier=ChatDuplicateVerifier(fake),
    )
    policy.assess(candidate, context | {"records": [record]})
    assert not sent


def test_semantic_provider_unavailable_defers(event, candidate, record, context):
    class Unavailable:
        def compare(self, *_):
            raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True)

    policy = AdmissionPolicy(
        RecordedEvidenceVerifier([(event, candidate, "supported")]),
        lambda _: event,
        duplicate_verifier=Unavailable(),
    )
    result = policy.assess(candidate, context | {"records": [comparable(candidate, record)]})
    assert result["outcome"] == "DEFER" and result["reason_codes"] == ["PROVIDER_UNAVAILABLE"]


def test_live_consolidation_interfaces_keep_complete_sources_and_citations():
    case = next(c for c in load_cases() if c["expected_proposals"] > 0)
    records = case["records"]
    ids = [r["memory"]["version"]["id"] for r in records]
    fake, sent = client([{"groups": [ids]}, {"support": "supported"}])
    result = Consolidator(ChatGroupingProvider(fake), ChatConsolidationVerifier(fake)).propose(
        records
    )
    assert len(result) == 1
    assert set(result[0]["source_version_ids"]) == set(ids)
    assert all(r["memory"]["version"]["content"] in result[0]["summary"] for r in records)
    assert len(sent) == 2


@pytest.mark.parametrize("support", ["unsupported", "uncertain"])
def test_real_verifier_interfaces_abstain_on_conflict_or_uncertainty(support):
    case = next(c for c in load_cases() if c["expected_proposals"] > 0)
    ids = [r["memory"]["version"]["id"] for r in case["records"]]
    fake, _ = client([{"groups": [ids]}, {"support": support}])
    assert (
        Consolidator(ChatGroupingProvider(fake), ChatConsolidationVerifier(fake)).propose(
            case["records"]
        )
        == []
    )


@pytest.mark.parametrize("fault", ["unknown", "duplicate", "missing", "empty"])
def test_grouping_rejects_invalid_source_partitions(fault):
    records = next(c for c in load_cases() if c["expected_proposals"] > 0)["records"]
    ids = [r["memory"]["version"]["id"] for r in records]
    groups = [ids]
    if fault == "unknown":
        groups = [["00000000-0000-0000-0000-000000000000"]]
    elif fault == "duplicate":
        groups = [ids, ids]
    elif fault == "missing":
        groups = [ids[:1]]
    else:
        groups = [ids, []]
    fake, _ = client([{"groups": groups}])
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        ChatGroupingProvider(fake).group(records)


def test_grouping_rejects_cross_project_before_provider():
    records = copy.deepcopy(next(c for c in load_cases() if c["expected_proposals"] > 0)["records"])
    records[0]["memory"]["project_id"] = "unrelated-project"
    fake, sent = client([])
    with pytest.raises(ModuleError, match="OUT_OF_SCOPE"):
        ChatGroupingProvider(fake).group(records)
    assert not sent


def test_condition_aliases_are_explicit_and_never_invent_values():
    original = {"project_version": "V1", "environment": "production"}
    assert normalize_conditions(original, {"project_version": "version"}) == {
        "version": "V1",
        "environment": "production",
    }
    assert original["project_version"] == "V1"
    assert normalize_conditions({}, {"project_version": "version"}) == {}
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        normalize_conditions(
            {"version": "V2", "project_version": "V1"}, {"project_version": "version"}
        )
