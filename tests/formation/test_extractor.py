import copy
import json

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.engine.modules import ModuleGateway
from contextbridge.formation import Extractor
from contextbridge.formation.extractor import MAX_OUTPUT_CHARACTERS
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider


def extractor(event, candidates, verdict="supported"):
    return Extractor(
        RecordedProvider(event, json.dumps(candidates)),
        RecordedEvidenceVerifier([(event, candidate, verdict) for candidate in candidates]),
    )


def assert_safe_failure(operation, code="INVALID_PROVIDER_OUTPUT", forbidden=""):
    with pytest.raises(ModuleError) as caught:
        operation()
    assert str(caught.value) == code
    assert caught.value.code == code
    assert not forbidden or forbidden not in str(caught.value)
    assert caught.value.__suppress_context__ or caught.value.__context__ is None


def test_shared_fixture_and_injected_engine_boundary(event, candidate):
    module = extractor(event, [candidate])
    assert module.extract(event) == [candidate]
    from contextbridge.contracts import CapturedEvent

    assert (
        ModuleGateway(extractor=module).extract(CapturedEvent.model_validate(event))[0].content
        == (candidate["content"])
    )


def test_filler_is_empty_not_a_provider_failure(event):
    event["messages"][0]["content"] = "Thanks!"
    assert extractor(event, []).extract(event) == []


def test_assistant_only_never_calls_model(event):
    class Uncalled:
        def generate(self, event):
            pytest.fail("Assistant-only input must not be sent to the model")

    event["messages"][0]["role"] = "assistant"
    assert Extractor(Uncalled(), RecordedEvidenceVerifier([])).extract(event) == []


@pytest.mark.parametrize("verdict", ["unsupported", "uncertain"])
def test_model_guess_does_not_pass_with_real_but_unrelated_quote(event, candidate, verdict):
    candidate["content"] = "The developer prefers Rust for every project."
    candidate["type"] = "PREFERENCE"
    assert_safe_failure(lambda: extractor(event, [candidate], verdict).extract(event))


def test_unlabelled_guess_cannot_pass_recorded_verifier(event, candidate):
    verifier = RecordedEvidenceVerifier([(event, copy.deepcopy(candidate), "supported")])
    candidate["content"] = "Use SQLite instead."
    module = Extractor(RecordedProvider(event, json.dumps([candidate])), verifier)
    assert_safe_failure(lambda: module.extract(event))


@pytest.mark.parametrize(
    "field,value",
    [
        ("project_id", "unrelated-project"),
        ("scope", "developer"),
        ("event_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("type", "GUESS"),
        ("content", ""),
        ("usefulness", float("inf")),
        ("confidence", "0.95"),
        ("confidence", True),
        ("valid_from", "2999-01-01T00:00:00Z"),
        ("valid_from", "2026-10-09T10:00:00"),
    ],
)
def test_invalid_candidate_is_rejected_even_if_fake_labels_supported(
    event, candidate, field, value
):
    candidate[field] = value
    assert_safe_failure(lambda: extractor(event, [candidate]).extract(event))


@pytest.mark.parametrize("mutation", ["unknown", "assistant", "excerpt", "agent", "duplicate-ref"])
def test_provenance_checks_are_independent_of_model_labels(event, candidate, mutation):
    if mutation == "unknown":
        candidate["evidence_refs"][0]["message_id"] = "missing"
    elif mutation == "assistant":
        event["messages"][0]["role"] = "assistant"
        event["messages"].append({"message_id": "filler", "role": "user", "content": "Thanks!"})
    elif mutation == "excerpt":
        candidate["source"]["evidence"] = "A quote that never occurred."
    elif mutation == "agent":
        candidate["source"]["agent"] = "different-agent"
    else:
        candidate["evidence_refs"] *= 2
    assert_safe_failure(lambda: extractor(event, [candidate]).extract(event))


@pytest.mark.parametrize("raw", ["not json", "{}", "null", "[NaN]", '[{"a":1,"a":2}]'])
def test_malformed_output_has_safe_error(event, raw):
    module = Extractor(RecordedProvider(event, raw), RecordedEvidenceVerifier([]))
    assert_safe_failure(lambda: module.extract(event))


def test_output_and_candidate_count_bounds(event, candidate):
    module = Extractor(
        RecordedProvider(event, " " * (MAX_OUTPUT_CHARACTERS + 1)), RecordedEvidenceVerifier([])
    )
    assert_safe_failure(lambda: module.extract(event))
    assert_safe_failure(lambda: extractor(event, [candidate] * 101).extract(event))
    assert_safe_failure(lambda: extractor(event, [candidate] * 2).extract(event))


@pytest.mark.parametrize("location", ["input", "output", "conditions", "metadata"])
def test_secrets_are_blocked_before_provider_or_return(event, candidate, location):
    secret = "sk-testsecret123456789012345"
    if location == "input":
        event["messages"][0]["content"] += " " + secret
        module = Extractor(RecordedProvider({}, "[]"), RecordedEvidenceVerifier([]))
        assert_safe_failure(lambda: module.extract(event), "INVALID_INPUT", secret)
        return
    if location == "output":
        candidate["source"]["evidence"] = secret
    elif location == "conditions":
        candidate["conditions"] = {"password": "private-value"}
    else:
        candidate["claim_key"] = secret
    assert_safe_failure(lambda: extractor(event, [candidate]).extract(event), forbidden=secret)


@pytest.mark.parametrize("failure", [TimeoutError, ConnectionError, RuntimeError])
def test_provider_exception_never_exposes_text(event, caplog, failure):
    class Failing:
        def generate(self, event):
            raise failure("private transcript and token")

    module = Extractor(Failing(), RecordedEvidenceVerifier([]))
    code = "INVALID_PROVIDER_OUTPUT" if failure is RuntimeError else "PROVIDER_UNAVAILABLE"
    assert_safe_failure(lambda: module.extract(event), code, "private transcript")
    assert "private transcript" not in caplog.text


def test_preserve_negation_filename_conditions_and_explicit_date(event, candidate):
    text = "Do not log tokens in auth/session.ts for production; effective 2026-10-08."
    event["messages"][0]["content"] = text
    candidate.update(content=text, conditions={"environment": "production"})
    candidate["valid_from"] = "2026-10-08T15:30:00+05:30"
    candidate["source"]["evidence"] = text
    from contextbridge.contracts import Candidate

    candidate = Candidate.model_validate(candidate).model_dump(mode="json")
    result = extractor(event, [candidate]).extract(event)[0]
    assert result["content"] == text
    assert result["conditions"] == {"environment": "production"}
    assert result["valid_from"] == "2026-10-08T10:00:00Z"


def test_verifier_cannot_mutate_returned_proposals_or_input(event, candidate):
    original = copy.deepcopy(event)

    class Mutating:
        def verify(self, candidate, event):
            candidate["content"] = "An unrelated guessed fact."
            event["project_id"] = "other"
            return "supported"

    result = Extractor(RecordedProvider(event, json.dumps([candidate])), Mutating()).extract(event)
    assert result == [candidate]
    assert event == original


def test_coerced_python_message_collection_still_screens_secrets(event):
    event["messages"] = (
        {"message_id": "m1", "role": "tool", "content": "password=do-not-store-this"},
    )
    module = Extractor(RecordedProvider({}, "[]"), RecordedEvidenceVerifier([]))
    assert_safe_failure(lambda: module.extract(event), "INVALID_INPUT")


def test_tool_evidence_is_accepted_but_cannot_be_mislabelled_as_user(event, candidate):
    event["messages"][0]["role"] = "tool"
    candidate["source"]["kind"] = "tool"
    assert extractor(event, [candidate]).extract(event) == [candidate]
    candidate["source"]["kind"] = "user"
    assert_safe_failure(lambda: extractor(event, [candidate]).extract(event))
