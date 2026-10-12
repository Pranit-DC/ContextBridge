import pytest

from contextbridge.retrieval import RetrievalConfig, Retriever
from contextbridge.retrieval.verifier import EvidenceVerifier
from tests.retrieval.fakes import (
    FakeEmbedder,
    FakeJudge,
    FakeRepository,
    FakeVerifier,
    inspection_for,
    make_record,
    match,
    query,
)


def build_repo(records):
    repo = FakeRepository(lexical=[match(r, "lexical", i) for i, r in enumerate(records, 1)])
    for record in records:
        repo.inspections[record["memory"]["id"]] = inspection_for(record)
    return repo


def run(records, verifier, q=None, **config):
    repo = build_repo(records)
    result = Retriever(RetrievalConfig(**config)).search(
        q or query(limit=5), repo, FakeEmbedder(), verifier
    )
    return result, repo


def labels(result):
    return [card["verification"] for card in result["cards"]]


def confident(**kw):
    record = make_record(**kw)
    record["confidence"] = 0.95
    return record


def test_without_a_verifier_nothing_is_verified_even_when_contested():
    result, repo = run([make_record(decision_state="contested")], None)
    assert labels(result) == ["not_requested"]
    assert repo.inspect_calls == []


def test_a_confident_clear_memory_is_not_inspected():
    verifier = FakeVerifier()
    result, repo = run([confident()], verifier)
    assert labels(result) == ["not_requested"]
    assert repo.inspect_calls == [] and verifier.calls == []


def test_contested_memory_is_verified_and_the_card_is_kept_with_its_label():
    record = make_record(decision_state="contested")
    verifier = FakeVerifier("uncertain")
    result, repo = run([record], verifier)
    assert labels(result) == ["uncertain"]
    assert result["cards"][0]["decision_state"] == "contested"
    sent_record, sent_inspection = verifier.calls[0]
    assert sent_record["memory"]["id"] == record["memory"]["id"]
    assert sent_inspection == repo.inspections[record["memory"]["id"]]


def test_low_confidence_memory_is_verified_and_can_be_supported():
    record = make_record()
    record["confidence"] = 0.3
    result, _ = run([record], FakeVerifier("supported"))
    assert labels(result) == ["supported"]


def test_memory_with_no_recorded_confidence_is_not_treated_as_doubtful():
    record = make_record()
    record["confidence"] = None
    result, _ = run([record], FakeVerifier())
    assert labels(result) == ["not_requested"]


def test_opted_in_memory_types_are_verified():
    decision = confident()
    decision["memory"]["type"] = "DECISION"
    fact = confident()
    fact["memory"]["type"] = "FACT"
    result, repo = run([decision, fact], FakeVerifier(), verify_types=frozenset({"DECISION"}))
    assert labels(result) == ["supported", "not_requested"]
    assert len(repo.inspect_calls) == 1


def test_verifications_per_search_are_bounded_and_the_limit_is_visible():
    records = [make_record(f"r{i}", decision_state="contested") for i in range(3)]
    result, repo = run(records, FakeVerifier(), max_verifications=1)
    assert sorted(labels(result)) == ["not_requested", "not_requested", "supported"]
    assert len(repo.inspect_calls) == 1
    assert "VERIFICATION_LIMIT_REACHED" in result["warnings"]
    assert result["degraded"] is False


def test_verification_never_removes_cards_or_exceeds_the_limit():
    records = [make_record(f"r{i}", decision_state="contested") for i in range(6)]
    result, _ = run(records, FakeVerifier("uncertain"), q=query(limit=4))
    assert len(result["cards"]) == 4


def test_failed_inspection_labels_the_card_uncertain_and_degrades_visibly():
    repo = build_repo([make_record(decision_state="contested")])
    repo.failing["inspect"] = RuntimeError("db down")
    result = Retriever().search(query(), repo, FakeEmbedder(), FakeVerifier("supported"))
    assert labels(result) == ["uncertain"]
    assert result["degraded"] is True and "VERIFICATION_UNAVAILABLE" in result["warnings"]


@pytest.mark.parametrize("verifier", [FakeVerifier(error=RuntimeError("x")), FakeVerifier("maybe")])
def test_a_failing_or_invalid_verifier_is_shown_as_uncertain(verifier):
    result, _ = run([make_record(decision_state="contested")], verifier)
    assert labels(result) == ["uncertain"]


def test_inspection_receives_the_same_resolved_query_as_the_channels():
    record = make_record(decision_state="contested")
    _, repo = run([record], FakeVerifier(), q=query(as_of=None))
    _, sent = repo.inspect_calls[0]
    assert sent["as_of"] is not None and sent["project_id"] == "contextbridge"


def test_real_verifier_is_supported_only_with_a_supporting_judge():
    record = make_record()
    record["confidence"] = 0.3
    supported, _ = run([record], EvidenceVerifier(FakeJudge("supports")))
    contradicted, _ = run([record], EvidenceVerifier(FakeJudge("contradicts")))
    unjudged, _ = run([record], EvidenceVerifier())
    assert labels(supported) == ["supported"]
    assert labels(contradicted) == labels(unjudged) == ["uncertain"]


def test_real_verifier_flags_a_record_that_changed_after_indexing():
    stale = make_record()
    stale["confidence"] = 0.3
    repo = build_repo([stale])
    # Inspection returns a different stored claim than the indexed card shows.
    repo.inspections[stale["memory"]["id"]]["history"][0]["content"] = "Changed after indexing."
    result = Retriever().search(
        query(), repo, FakeEmbedder(), EvidenceVerifier(FakeJudge("supports"))
    )
    assert labels(result) == ["uncertain"]


def test_hosted_judge_failure_keeps_card_with_visible_degradation():
    record = make_record()
    record["confidence"] = 0.3
    result, _ = run(
        [record], EvidenceVerifier(FakeJudge(error=RuntimeError("private provider failure")))
    )
    assert labels(result) == ["uncertain"]
    assert result["degraded"] and "VERIFICATION_UNAVAILABLE" in result["warnings"]


@pytest.mark.parametrize(
    "bad",
    [
        {"verify_below_confidence": 1.5},
        {"verify_below_confidence": -0.1},
        {"max_verifications": -1},
    ],
)
def test_invalid_verification_config_is_rejected(bad):
    with pytest.raises(ValueError):
        RetrievalConfig(**bad)
