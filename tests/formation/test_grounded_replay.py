"""Saved synthetic evidence exercises offline replay without credentials or model calls."""

from copy import deepcopy

import pytest

from contextbridge.engine.errors import ModuleError
from scripts.formation import evaluate, replay_grounded, review
from scripts.formation.execution import ExecutionTelemetry


def saved(name="groq-120b-v4.3-tuning-20261012"):
    dataset, digest = evaluate.load_dataset("tuning", root=evaluate.ROOT / "fresh-v2-20261012")
    run = evaluate.decode(evaluate.Run, evaluate.read_payload(evaluate.ROOT / f"{name}.json"))
    sidecar = evaluate.decode(
        ExecutionTelemetry,
        evaluate.read_payload(evaluate.ROOT / f"{name}.telemetry.json"),
    )
    return dataset, digest, run, sidecar


def test_replay_preserves_claims_decisions_and_source_execution(monkeypatch):
    from contextbridge.formation.providers.chat import ChatClient

    monkeypatch.setattr(
        ChatClient, "complete", lambda *_: pytest.fail("Replay must remain offline")
    )
    dataset, digest, source, sidecar = saved()
    original = deepcopy(source.model_dump(mode="json"))
    replay, execution = replay_grounded.replay(dataset, digest, source, sidecar)
    assert source.model_dump(mode="json") == original
    assert replay.mode == "postprocess_replay"
    assert replay.metadata.configuration["source_run_sha256"] == evaluate.dataset_digest(source)
    assert replay.metadata.configuration["new_provider_calls"] == 0
    assert execution["case_counts"]["completed_network_cases"] == 9
    assert execution["case_counts"]["local_only_cases"] == 3
    changes = []
    for before, after in zip(source.cases, replay.cases, strict=True):
        assert after.decisions == before.decisions
        assert after.error_code == before.error_code
        assert all(
            getattr(after, field) is None
            for field in ("latency_ms", "input_tokens", "output_tokens", "cost")
        )
        for old, new in zip(before.proposals, after.proposals, strict=True):
            fields = {
                key for key in type(old).model_fields if getattr(old, key) != getattr(new, key)
            }
            assert fields <= {"type", "valid_from"}
            if fields:
                changes.append((before.case_id, fields))
    assert changes == [
        ("tuning-v2-current-status", {"type"}),
        ("tuning-v2-dated-event", {"type", "valid_from"}),
    ]


@pytest.mark.parametrize("field", ["dataset_sha256", "run_sha256"])
def test_replay_rejects_changed_execution_hash(field):
    dataset, digest, source, sidecar = saved()
    setattr(sidecar, field, "0" * 64)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        replay_grounded.replay(dataset, digest, source, sidecar)


def test_replay_never_promotes_attempted_or_blocked_failures():
    dataset, digest, source, sidecar = saved("groq-120b-v4-tuning-20261012")
    result, execution = replay_grounded.replay(dataset, digest, source, sidecar)
    failed = [case for case in source.cases if case.error_code is not None]
    assert failed
    for case in failed:
        updated = next(c for c in result.cases if c.case_id == case.case_id)
        assert updated.proposals == case.proposals
        assert updated.decisions == []
        assert updated.error_code == case.error_code
    assert execution["case_counts"]["attempted_failed_network_cases"] == 1
    assert execution["case_counts"]["unattempted_cases"] == 9


def test_pending_human_review_cannot_turn_replay_into_independent_accuracy():
    dataset, digest, source, sidecar = saved()
    result, _ = replay_grounded.replay(dataset, digest, source, sidecar)
    packet = review.prepare(dataset, digest, result)
    assert packet.review_status == "pending"
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        review.score_review(dataset, digest, result, packet)
    # Source HTTP records cannot be attached to a changed replay hash.
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        replay_grounded.replay(dataset, digest, result, sidecar)


@pytest.mark.parametrize(
    "name,corpus,split,matched",
    [
        ("groq-120b-v4.3-tuning-20261012", "fresh-v2-20261012", "tuning", 8),
        ("groq-120b-v4.3-holdout-20261012", "fresh-v2-20261012", "holdout", 9),
        ("groq-120b-v4.4-tuning-replay-20261012", "fresh-v2-20261012", "tuning", 10),
        ("groq-120b-v4.4-holdout-replay-20261012", "fresh-v2-20261012", "holdout", 10),
        ("groq-120b-v4.4-focused-holdout-20261012", "fresh-v3-20261012", "holdout", 2),
    ],
)
def test_review_ready_scores_are_reproducible_and_never_claim_human_review(
    name, corpus, split, matched
):
    dataset, digest = evaluate.load_dataset(split, root=evaluate.ROOT / corpus)
    run = evaluate.decode(evaluate.Run, evaluate.read_payload(evaluate.ROOT / f"{name}.json"))
    root = evaluate.ROOT / "groq-120b-review-20261012"
    annotations = evaluate.decode(
        evaluate.Annotations, evaluate.read_payload(root / f"{name}.annotations-proposed.json")
    )
    sidecar = (
        evaluate.decode(
            ExecutionTelemetry,
            evaluate.read_payload(evaluate.ROOT / f"{name}.telemetry.json"),
        )
        if run.mode == "model_predictions"
        else None
    )
    score = evaluate.score(dataset, digest, run, annotations, execution_telemetry=sidecar)
    assert score["counts"]["matched_claims"] == matched
    assert score["results_kind"] == "provisional_agent_prediction_counts"
    assert score["independent_review_complete"] is False
    assert score["quality_gate"] == "pending"
    assert score["telemetry"]["cost"]["total"] is None
    packet = evaluate.decode(
        review.ReviewPacket, evaluate.read_payload(root / f"{name}.review-pending.json")
    )
    assert all(c.dataset_labels_approved is None for c in packet.cases)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        review.score_review(dataset, digest, run, packet, execution_telemetry=sidecar)
