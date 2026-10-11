"""Evaluation arithmetic and artifact binding; recorded labels are never model quality."""

import copy
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from contextbridge.engine.errors import ModuleError
from scripts.formation import evaluate as evaluation


@pytest.fixture
def bundle():
    dataset, digest = evaluation.load_dataset("tuning")
    run, annotations = evaluation.fixture_run(dataset, digest)
    return dataset, digest, run, annotations


def rescore(bundle):
    dataset, digest, run, annotations = bundle
    # Explicitly simulate a reviewer annotating this changed artifact, not stale review replay.
    annotations.run_sha256 = evaluation.dataset_digest(run)
    return evaluation.score(dataset, digest, run, annotations)


def test_fixed_splits_cover_types_and_have_distinct_inputs():
    tuning, _ = evaluation.load_dataset("tuning")
    holdout, _ = evaluation.load_dataset("holdout")
    evaluation.validate_splits(tuning, holdout)
    assert len(tuning.cases) == len(holdout.cases) == 12
    for dataset in (tuning, holdout):
        assert sum(len(case.expected_claims) for case in dataset.cases) == 10
        assert {claim.type.value for case in dataset.cases for claim in case.expected_claims} == {
            "FACT",
            "DECISION",
            "PREFERENCE",
            "STATE",
            "EVENT",
            "LESSON",
        }
        assert any(not case.expected_claims for case in dataset.cases)


def test_reusing_tuning_input_in_holdout_is_rejected():
    tuning, _ = evaluation.load_dataset("tuning")
    holdout, _ = evaluation.load_dataset("holdout")
    holdout.cases[0].event.messages = copy.deepcopy(tuning.cases[0].event.messages)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        evaluation.validate_splits(tuning, holdout)


def test_recorded_pipeline_checks_are_explicitly_fixture_only(bundle):
    report = evaluation.score(*bundle)
    assert report["results_kind"] == "recorded_fixture_counts"
    assert report["quality_gate"] == "pending"
    assert report["model_executed_by_runner"] is False
    assert report["counts"]["matched_claims"] == report["counts"]["expected_claims"] == 10
    assert report["counts"]["admission_errors"] == 0
    assert report["metadata"]["model_id"] is None
    assert all(field["missing_cases"] == 12 for field in report["telemetry"].values())
    assert all(field["total"] is None for field in report["telemetry"].values())


def test_paraphrase_requires_annotation_not_an_exact_content_match(bundle):
    run = bundle[2]
    run.cases[0].proposals[0].content = "The chosen primary store for Neptune is PostgreSQL."
    report = rescore(bundle)
    assert report["counts"]["matched_claims"] == 10


def test_repeated_predictions_cannot_inflate_recall(bundle):
    _, _, run, annotations = bundle
    duplicate = run.cases[0].proposals[0].model_copy(deep=True)
    duplicate.candidate_id = uuid4()
    decision = run.cases[0].decisions[0].model_copy(deep=True)
    decision.candidate_id = duplicate.candidate_id
    judgement = annotations.cases[0].judgements[0].model_copy(deep=True)
    judgement.candidate_id = duplicate.candidate_id
    run.cases[0].proposals.append(duplicate)
    run.cases[0].decisions.append(decision)
    annotations.cases[0].judgements.append(judgement)
    report = rescore(bundle)
    assert report["counts"]["proposals"] == 11
    assert report["rates"]["useful_claim_precision"] == pytest.approx(10 / 11)
    assert report["rates"]["useful_claim_recall"] == 1


@pytest.mark.parametrize("support,expected", [("unsupported", "REJECT"), ("uncertain", "DEFER")])
def test_unrelated_guess_and_admission_error_are_counted(bundle, support, expected):
    _, _, run, annotations = bundle
    run.cases[0].proposals[0].content = "Neptune uses Rust everywhere."
    judged = annotations.cases[0].judgements[0]
    judged.matched_claim_id = None
    judged.support = support
    judged.expected_admission = expected
    report = rescore(bundle)
    assert report["counts"]["matched_claims"] == 9
    assert report["counts"]["admission_errors"] == 1
    assert report["rates"][f"{support}_claim_rate"] == 0.1
    assert report["rates"]["useful_claim_recall"] == 0.9


def test_cross_scope_output_is_reported_as_a_hard_error(bundle):
    _, _, run, annotations = bundle
    run.cases[0].proposals[0].project_id = "other-project"
    judgement = annotations.cases[0].judgements[0]
    judgement.matched_claim_id = None
    judgement.support = "unsupported"
    judgement.expected_admission = "REJECT"
    report = rescore(bundle)
    assert report["counts"]["scope_errors"] == 1
    assert report["counts"]["provenance_errors"] == 1


def test_empty_denominators_are_missing_not_perfect_scores():
    dataset, _ = evaluation.load_dataset("tuning")
    dataset.cases = [next(case for case in dataset.cases if not case.expected_claims)]
    digest = evaluation.dataset_digest(dataset)
    run, annotations = evaluation.fixture_run(dataset, digest)
    report = evaluation.score(dataset, digest, run, annotations)
    assert all(rate is None for rate in report["rates"].values())


@pytest.mark.parametrize(
    "fault",
    [
        "missing-case",
        "duplicate-case",
        "missing-label",
        "unknown-label",
        "stale-review",
        "wrong-hash",
        "changed-dataset",
    ],
)
def test_incomplete_or_changed_artifacts_cannot_be_scored(bundle, fault):
    dataset, digest, run, annotations = bundle
    if fault == "missing-case":
        run.cases.pop()
    elif fault == "duplicate-case":
        run.cases[-1] = copy.deepcopy(run.cases[0])
    elif fault == "missing-label":
        annotations.cases[0].judgements.clear()
    elif fault == "unknown-label":
        annotations.cases[0].judgements[0].matched_claim_id = "holdout-unknown-claim"
    elif fault == "stale-review":
        run.cases[0].proposals[0].content = "Changed after review."
        with pytest.raises(ModuleError, match="INVALID_INPUT"):
            evaluation.score(dataset, digest, run, annotations)
        return
    elif fault == "wrong-hash":
        run.dataset_sha256 = "0" * 64
    else:
        dataset.cases[0].rationale = "Changed design label after the dataset was fixed."
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        rescore(bundle)


def test_partial_telemetry_is_not_reported_as_zero_or_complete(bundle):
    _, _, run, _ = bundle
    run.cases[0].latency_ms = 123.0
    run.cases[0].input_tokens = 0
    run.cases[0].output_tokens = 0
    run.cases[0].cost = 0.0
    run.metadata.cost_currency = "USD"
    report = rescore(bundle)
    assert report["telemetry"]["cost"] == {"recorded_cases": 1, "missing_cases": 11, "total": None}
    assert report["telemetry"]["input_tokens"]["recorded_cases"] == 1


def test_model_prediction_artifact_needs_observed_metadata_and_human_review(bundle):
    _, _, run, annotations = bundle
    run.mode = "model_predictions"
    annotations.label_source = "human_reviewed"
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        rescore(bundle)
    run.metadata.model_id = "test-supplied-model-id"
    run.metadata.prompt_version = "test-prompt-v1"
    run.metadata.recorded_at = datetime(2026, 10, 10, tzinfo=UTC)
    report = rescore(bundle)
    assert report["results_kind"] == "annotated_prediction_counts"
    assert report["model_executed_by_runner"] is False
    assert report["quality_gate"] == "pending"


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":1,"schema_version":2}',
        b'{"x":NaN}',
        b'{"password":"fixture-must-not-echo"}',
        b"not json",
    ],
)
def test_bad_json_or_secrets_have_safe_errors(raw, caplog):
    with pytest.raises(ModuleError, match="^INVALID_INPUT$") as caught:
        evaluation.decode(evaluation.Dataset, raw)
    assert caught.value.__suppress_context__
    assert "fixture-must-not-echo" not in caplog.text


def test_secret_metadata_cannot_be_echoed_even_from_typed_input(bundle):
    bundle[2].metadata.configuration = {"password": "fixture-must-not-echo"}
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        rescore(bundle)


def test_self_check_cli_omits_raw_evidence_and_claims_no_execution(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["evaluate", "--split", "holdout", "--self-check"])
    assert evaluation.main() == 0
    raw = capsys.readouterr().out
    report = json.loads(raw)
    assert report["split"] == "holdout"
    assert report["results_kind"] == "recorded_fixture_counts"
    assert report["model_executed_by_runner"] is False
    assert "2097152" not in raw


def test_saved_artifacts_cli_checks_exact_prediction_binding(bundle, tmp_path, monkeypatch, capsys):
    run_path, annotation_path = tmp_path / "run.json", tmp_path / "annotations.json"
    run_path.write_text(bundle[2].model_dump_json(), encoding="utf-8")
    annotation_path.write_text(bundle[3].model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv", ["evaluate", "--run", str(run_path), "--annotations", str(annotation_path)]
    )
    assert evaluation.main() == 0
    assert json.loads(capsys.readouterr().out)["quality_gate"] == "pending"
    bundle[2].cases[0].proposals[0].content = "Changed after labels were saved."
    run_path.write_text(bundle[2].model_dump_json(), encoding="utf-8")
    assert evaluation.main() == 1
    assert json.loads(capsys.readouterr().out) == {"error": "INVALID_INPUT"}


def test_failed_batch_reports_missing_admission_instead_of_success(bundle):
    _, _, run, _ = bundle
    run.cases[0].error_code = "INVALID_PROVIDER_OUTPUT"
    run.cases[0].decisions.clear()
    report = rescore(bundle)
    assert report["counts"]["failed_cases"] == 1
    assert report["counts"]["missing_decisions"] == 1
    assert report["counts"]["admission_decisions"] == 9
    assert report["quality_gate"] == "pending"


def test_failed_batch_cannot_also_claim_successful_admission(bundle):
    raw = bundle[2].model_dump(mode="json")
    raw["cases"][0]["error_code"] = "INVALID_PROVIDER_OUTPUT"
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        evaluation.decode(evaluation.Run, json.dumps(raw).encode())


def test_ground_truth_cannot_cite_an_assistant_as_authority(bundle):
    raw = bundle[0].model_dump(mode="json")
    raw["cases"][0]["event"]["messages"][0]["role"] = "assistant"
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        evaluation.decode(evaluation.Dataset, json.dumps(raw).encode())


def test_file_read_is_bounded_before_decode(tmp_path, monkeypatch):
    path = tmp_path / "oversize.json"
    path.write_bytes(b"x" * 1000)
    monkeypatch.setattr(evaluation, "MAX_INPUT_BYTES", 100)
    payload = evaluation.read_payload(path)
    assert len(payload) == 101
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        evaluation.decode(evaluation.Dataset, payload)


def test_fixed_dataset_content_change_requires_a_new_manifest(bundle, tmp_path, monkeypatch):
    dataset, digest, _, _ = bundle
    dataset.cases[0].rationale = "Changed after the fixed revision was recorded."
    (tmp_path / "tuning.json").write_text(dataset.model_dump_json(), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"splits": {"tuning": {"sha256": digest}}}), encoding="utf-8"
    )
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        evaluation.load_dataset("tuning")
