"""Corrected explanatory review copies preserve historical labels, hashes and provisional rates."""

import json

import pytest

from scripts.formation import evaluate
from scripts.formation.execution import ExecutionTelemetry

ROOT = evaluate.ROOT / "groq-120b-review-corrected-20261013"
PROVENANCE = json.loads((ROOT / "provenance.json").read_text(encoding="utf8"))


@pytest.mark.parametrize("entry", PROVENANCE["files"])
def test_rationale_corrections_are_source_accurate_without_changing_judgements(entry):
    original = evaluate.decode(
        evaluate.Annotations, evaluate.read_payload(evaluate.ROOT / entry["original_file"])
    )
    assert evaluate.dataset_digest(original) == entry["original_annotation_sha256"]
    corrected = evaluate.decode(
        evaluate.Annotations, evaluate.read_payload(ROOT / entry["corrected_file"])
    )
    name = entry["corrected_file"].removesuffix(".annotations-proposed.json")
    run = evaluate.decode(evaluate.Run, evaluate.read_payload(evaluate.ROOT / f"{name}.json"))
    corpus = "fresh-v3-20261012" if "focused" in name else "fresh-v2-20261012"
    dataset, digest = evaluate.load_dataset(run.split, root=evaluate.ROOT / corpus)
    examples = {case.case_id: case for case in dataset.cases}
    assert corrected.run_sha256 == original.run_sha256 == evaluate.dataset_digest(run)
    assert corrected.dataset_sha256 == original.dataset_sha256 == digest
    assert corrected.label_source == original.label_source == "agent_proposed"
    for before, after in zip(original.cases, corrected.cases, strict=True):
        for old, new in zip(before.judgements, after.judgements, strict=True):
            assert old.model_dump(exclude={"rationale"}) == new.model_dump(exclude={"rationale"})
            if old.rationale != new.rationale:
                event = examples[after.case_id].event
                assert event.messages[0].role == "user"
                if after.case_id.endswith("adopted-cache"):
                    assert "choose" in event.messages[0].content
                    assert "MongoDB" in event.messages[1].content
                    assert (
                        "directly chooses" in new.rationale and "neither adopted" in new.rationale
                    )
                else:
                    assert "currently" in event.messages[0].content
                    assert "actual source is a user, not a tool" in new.rationale
    sidepath = evaluate.ROOT / f"{name}.telemetry.json"
    sidecar = (
        evaluate.decode(ExecutionTelemetry, evaluate.read_payload(sidepath))
        if sidepath.exists()
        else None
    )
    report = evaluate.score(dataset, digest, run, corrected, execution_telemetry=sidecar)
    previous = json.loads(
        (evaluate.ROOT / "groq-120b-review-20261012" / f"{name}.score-provisional.json").read_text()
    )
    assert report["counts"] == previous["counts"] and report["rates"] == previous["rates"]
    assert report["quality_gate"] == "pending" and report["independent_review_complete"] is False
