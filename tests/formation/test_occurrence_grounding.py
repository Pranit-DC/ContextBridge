"""Review reproductions: uncertainty cannot supply local EVENT/time proof or bypass an audit."""

import json

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.grounded import (
    BatchVerifier,
    GroundedProvider,
    literal_metadata,
)
from tests.formation.test_grounded_provider import check, client, wire

UNCONFIRMED = (
    "could have completed",
    "should have completed",
    "wasn’t completed",
    "has no confirmation of being completed",
    "may have finished",
    "might have finished",
)
OCCURRENCE = "2026-10-11T07:20:00Z"
CAPTURE = "2026-10-12T08:00:00Z"
CHECKED = "2026-10-12T09:00:00Z"


def uncertain_event(event, candidate, wording):
    quote = f"{event['project_id']} backup restore {wording} at {OCCURRENCE}."
    event["occurred_at"] = CAPTURE
    event["messages"][0].update(role="tool", content=quote)
    candidate.update(type="FACT", content=quote, valid_from=CAPTURE, claim_key=None)
    candidate["source"].update(kind="tool", evidence=quote)
    return quote


@pytest.mark.parametrize("wording", UNCONFIRMED)
def test_uncertain_occurrence_does_not_change_metadata_or_bypass_disagreeing_audit(
    event, candidate, wording
):
    quote = uncertain_event(event, candidate, wording)
    assert literal_metadata(quote, quote, event["project_id"], "tool") == (None, None)
    fake, sent = client(
        [
            {"claims": [wire(candidate)]},
            {"checks": [check(candidate, kind="STATE")]},
        ]
    )
    provider, verifier = GroundedProvider(fake), BatchVerifier(fake)
    produced = json.loads(provider.generate(event))[0]
    assert produced["content"] == quote
    assert produced["type"] == "FACT" and produced["valid_from"] == CAPTURE
    assert provider.type_corrections == provider.time_corrections == 0
    assert verifier.verify(produced, event) == "unsupported"
    decision = AdmissionPolicy(verifier, lambda _: event).assess(
        produced, {"schema_version": 1, "checked_at": CHECKED, "records": []}
    )
    assert decision["outcome"] == "REJECT"
    assert decision["reason_codes"] == ["UNSUPPORTED_CLAIM"]
    assert len(sent) == 2  # Admission reuses only this exact hash-bound audit verdict.

    fake, _ = client(
        [
            {"claims": [wire(candidate)]},
            {"checks": [check(candidate, kind="STATE")]},
        ]
    )
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Extractor(GroundedProvider(fake), BatchVerifier(fake)).extract(event)


@pytest.mark.parametrize(
    "wording", ["completed", "finished successfully", "was completed", "has completed"]
)
def test_positive_occurrence_can_still_supply_category_and_source_time(wording):
    quote = f"Cedar backup restore {wording} at {OCCURRENCE}."
    kind, when = literal_metadata(quote, quote, "cedar", "tool")
    assert kind == "EVENT" and when.isoformat() == "2026-10-11T07:20:00+00:00"


def test_relative_speculation_is_not_resolved_to_a_guessed_occurrence_date():
    quote = "Cedar backup restore could have finished yesterday."
    assert literal_metadata(quote, quote, "cedar", "tool") == (None, None)


@pytest.mark.parametrize("prefix", ["It is possible that", "There is no confirmation that"])
def test_positive_excerpt_cannot_hide_uncertainty_in_the_complete_source(prefix, event, candidate):
    quote = uncertain_event(event, candidate, "completed")
    event["messages"][0]["content"] = f"{prefix} {quote}"
    fake, _ = client(
        [
            {"claims": [wire(candidate)]},
            {"checks": [check(candidate, kind="STATE")]},
        ]
    )
    provider, verifier = GroundedProvider(fake), BatchVerifier(fake)
    produced = json.loads(provider.generate(event))[0]
    assert produced["type"] == "FACT" and produced["valid_from"] == CAPTURE
    assert verifier.verify(produced, event) == "unsupported"


@pytest.mark.parametrize("support,outcome", [("unsupported", "REJECT"), ("uncertain", "DEFER")])
def test_positive_metadata_proof_never_overrides_a_negative_support_verdict(
    support, outcome, event, candidate
):
    uncertain_event(event, candidate, "completed")
    fake, _ = client(
        [
            {"claims": [wire(candidate)]},
            {"checks": [check(candidate, kind="STATE", support=support)]},
        ]
    )
    provider, verifier = GroundedProvider(fake), BatchVerifier(fake)
    produced = json.loads(provider.generate(event))[0]
    assert produced["type"] == "EVENT" and produced["valid_from"] == OCCURRENCE
    assert (
        AdmissionPolicy(verifier, lambda _: event).assess(
            produced, {"schema_version": 1, "checked_at": CHECKED, "records": []}
        )["outcome"]
        == outcome
    )
