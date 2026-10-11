import copy

import pytest

from contextbridge.retrieval.verifier import EvidenceVerifier
from tests.retrieval.fakes import FakeJudge, inspection_for, make_record


def verify(record, inspection, judge="default"):
    judge = FakeJudge() if judge == "default" else judge
    return EvidenceVerifier(judge).verify(record, inspection)


def test_supported_only_when_the_record_matches_and_the_judge_agrees():
    record = make_record()
    judge = FakeJudge("supports")
    assert verify(record, inspection_for(record), judge) == "supported"
    claim, evidence = judge.calls[0]
    assert claim == record["memory"]["version"]["content"]
    assert evidence == record["memory"]["version"]["source"]["evidence"]


@pytest.mark.parametrize("outcome", ["contradicts", "insufficient", "maybe", None, 3])
def test_any_judgment_other_than_supports_is_uncertain(outcome):
    record = make_record()
    assert verify(record, inspection_for(record), FakeJudge(outcome)) == "uncertain"


def test_without_a_judge_provenance_alone_is_never_called_supported():
    record = make_record()
    assert verify(record, inspection_for(record), judge=None) == "uncertain"


def test_a_failing_judge_is_uncertain_and_does_not_raise():
    record = make_record()
    judge = FakeJudge(error=RuntimeError("provider detail"))
    assert verify(record, inspection_for(record), judge) == "uncertain"


def test_contested_records_are_never_supported_and_the_judge_is_not_asked():
    record = make_record(decision_state="contested")
    judge = FakeJudge()
    assert verify(record, inspection_for(record), judge) == "uncertain"
    assert judge.calls == []


def mutated(record, path, value):
    changed = copy.deepcopy(record)
    target = changed["memory"]["version"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (["content"], "A different claim."),
        (["status"], "SUPERSEDED"),
        (["number"], 2),
        (["valid_from"], "2026-10-01T00:00:00Z"),
        (["valid_to"], "2026-10-12T00:00:00Z"),
        (["source", "evidence"], "Other evidence."),
        (["source", "agent"], "someone-else"),
    ],
)
def test_inspection_that_disagrees_with_the_card_is_uncertain(path, value):
    record = make_record()
    stale_inspection = inspection_for(mutated(record, path, value))
    stale_inspection["memory"]["id"] = record["memory"]["id"]
    assert verify(record, stale_inspection) == "uncertain"


def test_inspection_of_a_different_memory_is_uncertain():
    record, other = make_record(), make_record()
    assert verify(record, inspection_for(other)) == "uncertain"


def test_inspection_missing_the_cards_version_is_uncertain():
    record = make_record()
    assert verify(record, inspection_for(record, history=[])) == "uncertain"


def test_a_historical_card_is_checked_against_its_own_version():
    old = make_record(
        "uses PostgreSQL",
        status="SUPERSEDED",
        valid_from="2026-10-01T00:00:00Z",
        valid_to="2026-10-05T00:00:00Z",
    )
    new = copy.deepcopy(old)
    new["memory"]["version"].update(
        id="99999999-9999-4999-8999-999999999999",
        number=2,
        content="uses SQLite",
        status="ACTIVE",
        valid_from="2026-10-05T00:00:00Z",
        valid_to=None,
    )
    history = [old["memory"]["version"], new["memory"]["version"]]
    assert verify(old, inspection_for(old, history=history)) == "supported"


def test_evidence_containing_a_credential_is_not_sent_to_the_judge():
    record = make_record()
    record["memory"]["version"]["source"]["evidence"] = "key sk-abcdefghijklmnopqrstuvwxyz here"
    judge = FakeJudge()
    assert verify(record, inspection_for(record), judge) == "uncertain"
    assert judge.calls == []


@pytest.mark.parametrize("bad", [None, "text", {}, {"memory": 1}])
def test_malformed_input_is_uncertain_rather_than_an_error(bad):
    record = make_record()
    assert verify(bad, inspection_for(record)) == "uncertain"
    assert verify(record, bad) == "uncertain"
