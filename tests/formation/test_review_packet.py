import copy

import pytest

from contextbridge.engine.errors import ModuleError
from scripts.formation.evaluate import fixture_run, load_dataset
from scripts.formation.review import ReviewPacket, prepare, render, score_review


@pytest.fixture
def inputs():
    dataset, digest = load_dataset("tuning")
    run, _ = fixture_run(dataset, digest)
    # Synthetic predictions/attestations exercise the review boundary, never model quality.
    run.mode = "model_predictions"
    run.metadata.model_id = "synthetic-model"
    run.metadata.prompt_version = "synthetic-prompt"
    run.metadata.recorded_at = dataset.cases[0].context.checked_at
    return dataset, digest, run


def synthetic_review(dataset, digest, run):
    packet = prepare(dataset, digest, run).model_dump(mode="json")
    packet.update(
        review_status="completed",
        reviewer="Pranit",
        reviewed_at="2026-10-11T10:00:00Z",
        review_evidence="Synthetic test attestation only; not an actual review.",
    )
    for reviewed, example in zip(packet["cases"], dataset.cases, strict=True):
        reviewed["dataset_labels_approved"] = True
        for judgement, expected in zip(
            reviewed["judgements"], example.expected_claims, strict=True
        ):
            judgement.update(
                matched_claim_id=expected.claim_id,
                support="supported",
                expected_admission=expected.expected_admission,
                rationale="Synthetic reviewer assertion for a boundary test.",
            )
    return packet


def test_packet_has_no_fabricated_judgements_or_approval(inputs):
    dataset, digest, run = inputs
    packet = prepare(dataset, digest, run)
    assert packet.review_status == "pending"
    assert packet.reviewer is packet.reviewed_at is packet.review_evidence is None
    assert all(case.dataset_labels_approved is None for case in packet.cases)
    assert all(item.support is None for case in packet.cases for item in case.judgements)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        score_review(dataset, digest, run, packet)
    text = render(dataset, run, packet)
    assert "comparison_context" in text
    assert "design_labels_pending_review" in text
    assert "not authentication" in text


@pytest.mark.parametrize("mutation", ["hash", "reviewer", "evidence", "empty-case", "judgement"])
def test_incomplete_or_mismatched_review_cannot_produce_scores(inputs, mutation):
    dataset, digest, run = inputs
    payload = synthetic_review(dataset, digest, run)
    if mutation == "hash":
        payload["run_sha256"] = "0" * 64
    elif mutation == "reviewer":
        payload["reviewer"] = "Unassigned reviewer"
    elif mutation == "evidence":
        payload["review_evidence"] = None
    elif mutation == "empty-case":
        next(case for case in payload["cases"] if not case["judgements"])[
            "dataset_labels_approved"
        ] = None
    else:
        payload["cases"][0]["judgements"][0]["support"] = None
    packet = ReviewPacket.model_validate(payload)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        score_review(dataset, digest, run, packet)


def test_complete_review_scores_but_does_not_claim_quality_gate_passed(inputs):
    dataset, digest, run = inputs
    packet = ReviewPacket.model_validate(synthetic_review(dataset, digest, run))
    report = score_review(dataset, digest, run, packet)
    assert report["rates"]["useful_claim_recall"] == 1
    assert report["quality_gate"] == "pending"
    assert report["model_executed_by_runner"] is False
    assert report["dataset_label_status"] == "design_labels_pending_team_review"
    changed = copy.deepcopy(run)
    changed.cases[0].proposals[0].content = "Changed interpretation after review."
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        score_review(dataset, digest, changed, packet)
