import copy
import json

import pytest

from contextbridge.formation import AdmissionPolicy
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier

from .conftest import FIXTURES


def policy(event, candidate, verdict="supported", **kwargs):
    return AdmissionPolicy(
        RecordedEvidenceVerifier([(event, candidate, verdict)]),
        lambda event_id: copy.deepcopy(event) if event_id == event["event_id"] else None,
        **kwargs,
    )


def test_agreed_admission_fixture(event, candidate, context):
    expected = json.loads((FIXTURES / "admission-decision.json").read_text(encoding="utf-8"))
    assert policy(event, candidate).assess(candidate, context) == expected


@pytest.mark.parametrize("verdict,outcome", [("unsupported", "REJECT"), ("uncertain", "DEFER")])
def test_unrelated_quote_is_not_authoritative(event, candidate, context, verdict, outcome):
    candidate["content"] = "The developer prefers Rust everywhere."
    assert policy(event, candidate, verdict).assess(candidate, context)["outcome"] == outcome


def test_missing_original_event_is_deferred(event, candidate, context):
    module = AdmissionPolicy(RecordedEvidenceVerifier([]), lambda _: None)
    assert module.assess(candidate, context)["reason_codes"] == ["INSUFFICIENT_EVIDENCE"]


def test_exact_duplicate_has_no_mutation_and_correction_is_only_admitted(
    event, candidate, context, record
):
    context["records"] = [record]
    before = copy.deepcopy(context)
    assert policy(event, candidate).assess(candidate, context)["reason_codes"] == ["DUPLICATE"]
    assert context == before
    text = "Correction: ContextBridge now uses SQLite as its primary database."
    event["messages"][0]["content"] = text
    candidate["content"] = text
    candidate["source"]["evidence"] = text
    assert policy(event, candidate).assess(candidate, context)["outcome"] == "ADMIT"
    assert context == before


@pytest.mark.parametrize("difference", ["project", "conditions", "type", "stale", "contested"])
def test_same_text_is_not_a_global_duplicate(event, candidate, context, record, difference):
    if difference == "project":
        record["memory"]["project_id"] = "other-project"
    elif difference == "conditions":
        record["memory"]["conditions"] = {"environment": "production"}
    elif difference == "type":
        record["memory"]["type"] = "STATE"
    elif difference == "stale":
        record["memory"]["current_version"] = 2
    else:
        record["decision_state"] = "contested"
    context["records"] = [record]
    assert policy(event, candidate).assess(candidate, context)["outcome"] == "ADMIT"


def test_source_provenance_rechecked_and_secrets_rejected(event, candidate, context):
    candidate["evidence_refs"][0]["message_id"] = "missing"
    assert policy(event, candidate).assess(candidate, context)["outcome"] == "REJECT"
    candidate["content"] = "password=do-not-save-this"
    assert policy(event, candidate).assess(candidate, context)["reason_codes"] == [
        "SECRET_DETECTED"
    ]


@pytest.mark.parametrize(
    "field,value,outcome", [("confidence", 0.2, "DEFER"), ("usefulness", 0.1, "REJECT")]
)
def test_scores_cannot_override_evidence_and_are_configurable(
    event, candidate, context, field, value, outcome
):
    candidate[field] = value
    assert policy(event, candidate).assess(candidate, context)["outcome"] == outcome
    assert (
        policy(event, candidate, min_confidence=0.1, min_usefulness=0.1).assess(candidate, context)[
            "outcome"
        ]
        == "ADMIT"
    )


def test_one_important_rare_lesson_is_not_discarded(event, candidate, context):
    text = "Never log session tokens: auth/session.ts previously exposed them in error output."
    event["messages"][0]["content"] = text
    candidate.update(type="LESSON", content=text)
    candidate["source"]["evidence"] = text
    assert policy(event, candidate).assess(candidate, context)["outcome"] == "ADMIT"


def test_unavailable_verifier_is_defer_not_success(event, candidate, context):
    class Unavailable:
        def verify(self, candidate, event):
            raise TimeoutError("private source text")

    result = AdmissionPolicy(Unavailable(), lambda _: event).assess(candidate, context)
    assert result["outcome"] == "DEFER"
    assert result["reason_codes"] == ["PROVIDER_UNAVAILABLE"]


def test_uncertain_effective_time_is_deferred(event, candidate, context):
    context["checked_at"] = "2026-10-08T10:00:00Z"
    assert policy(event, candidate).assess(candidate, context)["reason_codes"] == ["AMBIGUOUS_TIME"]


@pytest.mark.parametrize("value", [-1, 2, float("nan"), float("inf"), True, None, "0.8"])
def test_invalid_threshold_is_not_a_policy(event, candidate, value):
    with pytest.raises(ValueError):
        policy(event, candidate, min_confidence=value)


@pytest.mark.parametrize("value", [0, 1])
def test_policy_threshold_endpoints_are_inclusive(event, candidate, context, value):
    candidate.update(confidence=float(value), usefulness=float(value))
    result = policy(event, candidate, min_confidence=value, min_usefulness=value).assess(
        candidate, context
    )
    assert result["outcome"] == "ADMIT"


def test_uncertain_support_is_not_overridden_by_uselessness(event, candidate, context):
    candidate.update(usefulness=0, confidence=0)
    assert policy(event, candidate, "uncertain").assess(candidate, context) == {
        "schema_version": 1,
        "candidate_id": candidate["candidate_id"],
        "outcome": "DEFER",
        "reason_codes": ["INSUFFICIENT_EVIDENCE"],
    }


@pytest.mark.parametrize("field", ["created_at", "recorded_at"])
def test_recorded_after_snapshot_cannot_reject_duplicate(event, candidate, context, record, field):
    if field == "created_at":
        record["memory"][field] = "2026-10-09T12:00:00Z"
    else:
        record["memory"]["version"][field] = "2026-10-09T12:00:00Z"
    context["records"] = [record]
    assert policy(event, candidate).assess(candidate, context)["outcome"] == "ADMIT"


@pytest.mark.parametrize("end", ["2026-10-09T11:00:00Z", "2026-10-09T11:00:01Z"])
def test_duplicate_validity_interval_is_half_open(event, candidate, context, record, end):
    record["memory"]["version"]["valid_to"] = end
    context["records"] = [record]
    outcome = policy(event, candidate).assess(candidate, context)["outcome"]
    assert outcome == ("REJECT" if end.endswith("01Z") else "ADMIT")


def test_evidence_failures_are_safe_before_scores_or_comparison(event, candidate, context, record):
    candidate.update(confidence=1.0, usefulness=1.0)
    context["records"] = [record]
    assert policy(event, candidate, "unsupported").assess(candidate, context)["reason_codes"] == [
        "UNSUPPORTED_CLAIM"
    ]
