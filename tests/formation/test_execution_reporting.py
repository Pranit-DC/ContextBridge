"""Offline regression evidence; accepted reviews are copied unchanged from Pranit's commit."""

import copy
import json
from pathlib import Path

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from scripts.formation import evaluate, review
from scripts.formation.execution import ExecutionTelemetry, summarize_execution

ROOT = Path(__file__).resolve().parents[2] / "evaluation/formation"
REVIEWS = ROOT / "pranit-reviewed-20261012"
SEQUENTIAL = "apodex-tuning-sequential-20261012"


def bundle(name=SEQUENTIAL, split="tuning"):
    dataset, digest = evaluate.load_dataset(split)
    run = evaluate.decode(evaluate.Run, evaluate.read_payload(ROOT / f"{name}.json"))
    packet = evaluate.decode(
        review.ReviewPacket, evaluate.read_payload(REVIEWS / f"{name}.review-completed.json")
    )
    return dataset, digest, run, packet


def sidecar():
    return json.loads((ROOT / f"{SEQUENTIAL}.telemetry.json").read_text(encoding="utf-8"))


def decoded(payload):
    return evaluate.decode(ExecutionTelemetry, json.dumps(payload).encode())


@pytest.fixture(autouse=True)
def no_provider_requests(monkeypatch):
    monkeypatch.setattr(httpx.Client, "send", lambda *args, **kwargs: pytest.fail("Offline only"))


def test_real_saved_sequential_breakdown_preserves_overall_recall_and_unknown_usage():
    report = review.score_review(*bundle(), execution_telemetry=decoded(sidecar()))
    assert report["execution"]["case_counts"] == {
        "completed_network_cases": 1,
        "attempted_failed_network_cases": 1,
        "unattempted_cases": 9,
        "provider_stop_cases": 9,
        "call_budget_cases": 0,
        "local_only_cases": 1,
        "unknown_cases": 0,
    }
    assert report["execution"]["recorded_calls"] == 3
    assert report["counts"]["failed_cases"] == report["counts"]["cases_with_error_code"] == 10
    assert "not failed model executions" in report["counter_definitions"]["failed_cases"]
    assert report["counts"]["matched_claims"] == 1
    assert report["counts"]["expected_claims"] == 10
    assert report["rates"]["useful_claim_recall"] == 0.1
    assert report["quality_gate"] == "pending"
    assert report["model_executed_by_runner"] is False
    assert report["telemetry"]["cost"]["total"] is None
    assert report["telemetry"]["input_tokens"]["total"] is None
    assert report["telemetry"]["output_tokens"]["total"] is None
    assert decoded(sidecar()).calls[2].observed_model is None


@pytest.mark.parametrize(
    "name,split,recall,errors",
    [
        ("openrouter-tuning-live-20261011", "tuning", 0.3, 6),
        ("openrouter-holdout-live-20261011", "holdout", 0.1, 8),
        ("gemma-tuning-baseline-20261011", "tuning", 0.0, 11),
        (SEQUENTIAL, "tuning", 0.1, 10),
    ],
)
def test_saved_runs_without_sidecar_have_unknown_execution_not_inferred_attempts(
    name, split, recall, errors
):
    report = review.score_review(*bundle(name, split))
    counts = report["execution"]["case_counts"]
    assert counts["unknown_cases"] == 12
    assert all(count == 0 for key, count in counts.items() if key != "unknown_cases")
    assert report["execution"]["recorded_calls"] is None
    assert all(case["attempted_calls"] is None for case in report["execution"]["cases"])
    assert report["counts"]["cases_with_error_code"] == errors
    assert report["rates"]["useful_claim_recall"] == recall


def test_old_call_only_sidecar_identifies_recorded_attempts_but_not_missing_case_status():
    inputs = bundle("gemma-tuning-baseline-20261011")
    telemetry = evaluate.decode(
        ExecutionTelemetry,
        evaluate.read_payload(ROOT / "gemma-tuning-baseline-20261011.telemetry.json"),
    )
    report = review.score_review(*inputs, execution_telemetry=telemetry)
    counts = report["execution"]["case_counts"]
    assert counts["attempted_failed_network_cases"] == 11
    assert counts["unknown_cases"] == 1
    assert counts["local_only_cases"] == counts["unattempted_cases"] == 0
    assert report["execution"]["evidence"] == "validated_call_records"
    assert report["rates"]["useful_claim_recall"] == 0


def test_call_records_without_case_records_do_not_invent_a_provider_stop():
    payload = sidecar()
    del payload["cases"], payload["execution"]
    report = review.score_review(*bundle(), execution_telemetry=decoded(payload))
    counts = report["execution"]["case_counts"]
    assert counts["completed_network_cases"] == counts["attempted_failed_network_cases"] == 1
    assert counts["unknown_cases"] == 10
    assert counts["unattempted_cases"] == counts["local_only_cases"] == 0


FAULTS = [
    "bool-version",
    "bool-latency",
    "bool-cost",
    "dataset-hash",
    "run-hash",
    "prompt",
    "duplicate-case",
    "unknown-case",
    "missing-case",
    "unknown-call-case",
    "call-index",
    "call-count",
    "empty-attempt",
    "fake-local",
    "missing-calls",
    "stage",
    "requested-model",
    "success-retryable",
    "success-http-error",
    "negative-latency",
    "nonfinite-cost",
    "bool-token",
    "wrong-usage",
    "wrong-cost",
    "unknown-field",
    "partial-profile",
    "partial-cases",
    "concurrency",
    "budget",
    "disabled-stop",
    "string-count",
    "call-after-stop",
    "verification-before-extraction",
]


def malformed(payload, fault):
    if fault == "bool-version":
        payload["schema_version"] = True
    elif fault == "bool-latency":
        payload["calls"][0]["latency_ms"] = True
    elif fault == "bool-cost":
        payload["calls"][0]["cost_usd"] = False
    elif fault in ("dataset-hash", "run-hash"):
        payload[fault.replace("-hash", "_sha256")] = "0" * 64
    elif fault == "prompt":
        payload["prompt_version"] = "wrong-prompt"
    elif fault == "duplicate-case":
        payload["cases"][-1] = copy.deepcopy(payload["cases"][0])
    elif fault == "unknown-case":
        payload["cases"][-1]["case_id"] = "unknown-case"
    elif fault == "missing-case":
        payload["cases"].pop()
    elif fault == "unknown-call-case":
        payload["calls"][0]["case_id"] = "unknown-case"
    elif fault == "call-index":
        payload["calls"][1]["call_index"] = 1
    elif fault == "call-count":
        payload["cases"][0]["attempted_calls"] = 1
    elif fault == "empty-attempt":
        payload["cases"][2]["execution"] = "attempted"
    elif fault == "fake-local":
        payload["cases"][2]["execution"] = "local_only"
    elif fault == "missing-calls":
        payload["calls"].clear()
    elif fault == "stage":
        payload["calls"][0]["stage"] = "persistence"
    elif fault == "requested-model":
        payload["calls"][0]["requested_model"] = "another/model:free"
    elif fault == "success-retryable":
        payload["calls"][0]["retryable"] = True
    elif fault == "success-http-error":
        payload["calls"][0]["http_status"] = 429
    elif fault == "negative-latency":
        payload["calls"][0]["latency_ms"] = -1
    elif fault == "nonfinite-cost":
        payload["calls"][0]["cost_usd"] = float("nan")
    elif fault == "bool-token":
        payload["calls"][0]["input_tokens"] = True
    elif fault == "wrong-usage":
        payload["calls"][0]["input_tokens"] += 1
    elif fault == "wrong-cost":
        payload["calls"][0]["cost_usd"] = 1
    elif fault == "unknown-field":
        payload["calls"][0]["raw_response"] = "discard this"
    elif fault == "partial-profile":
        del payload["execution"]
    elif fault == "partial-cases":
        del payload["cases"]
    elif fault == "concurrency":
        payload["execution"]["concurrency"] = 2
    elif fault == "budget":
        payload["execution"]["max_calls"] = 2
    elif fault == "disabled-stop":
        payload["execution"]["stop_on_provider_unavailable"] = False
    elif fault == "string-count":
        payload["cases"][0]["attempted_calls"] = "2"
    elif fault == "call-after-stop":
        call = copy.deepcopy(payload["calls"][0])
        call.update(call_index=4, case_id=payload["cases"][2]["case_id"])
        payload["calls"].append(call)
    elif fault == "verification-before-extraction":
        payload["calls"][0]["stage"] = "verification"
    return payload


@pytest.mark.parametrize("fault", FAULTS)
def test_malformed_or_inconsistent_telemetry_cannot_be_scored(fault):
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        review.score_review(*bundle(), execution_telemetry=decoded(malformed(sidecar(), fault)))


@pytest.mark.parametrize("field", ["latency_ms", "input_tokens", "output_tokens", "cost"])
def test_unattempted_case_cannot_have_invented_usage_or_latency(field):
    dataset, digest, run, _ = bundle()
    setattr(run.cases[2], field, 0)
    payload = sidecar()
    payload["run_sha256"] = evaluate.dataset_digest(run)
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        summarize_execution(dataset, digest, run, decoded(payload))


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_large_token_totals_require_exact_agreement(field):
    dataset, digest, run, _ = bundle()
    payload = sidecar()
    payload["calls"][0][field] = 999_990_000
    total = sum(call[field] for call in payload["calls"][:2])
    setattr(run.cases[0], field, total + 1)
    payload["run_sha256"] = evaluate.dataset_digest(run)
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        summarize_execution(dataset, digest, run, decoded(payload))


def test_provider_stop_requires_an_earlier_unavailable_call():
    dataset, digest, run, _ = bundle()
    run.cases[1].error_code = "INVALID_PROVIDER_OUTPUT"
    payload = sidecar()
    payload["run_sha256"] = evaluate.dataset_digest(run)
    payload["calls"][2]["error_code"] = "INVALID_PROVIDER_OUTPUT"
    payload["calls"][2]["retryable"] = False
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        summarize_execution(dataset, digest, run, decoded(payload))


def test_call_budget_status_requires_exhaustion_not_provider_failure():
    dataset, digest, run, _ = bundle()
    run.cases[2].error_code = "CANCELLED"
    payload = sidecar()
    payload["run_sha256"] = evaluate.dataset_digest(run)
    payload["cases"][2]["execution"] = "call_budget"
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        summarize_execution(dataset, digest, run, decoded(payload))


def test_exhausted_budget_is_counted_separately_and_local_case_stays_local():
    dataset, digest, run, _ = bundle()
    payload = sidecar()
    payload["execution"]["max_calls"] = 3
    for prediction, record in zip(run.cases, payload["cases"], strict=True):
        if record["execution"] == "provider_stop":
            prediction.error_code = "CANCELLED"
            record["execution"] = "call_budget"
    payload["run_sha256"] = evaluate.dataset_digest(run)
    result = summarize_execution(dataset, digest, run, decoded(payload))
    assert result["case_counts"]["call_budget_cases"] == 9
    assert result["case_counts"]["provider_stop_cases"] == 0
    assert result["case_counts"]["local_only_cases"] == 1


@pytest.mark.parametrize(
    "fault", ["unapproved-empty-case", "missing-judgement", "pending", "changed-run"]
)
def test_execution_evidence_does_not_bypass_review_requirements(fault):
    dataset, digest, run, packet = bundle()
    if fault == "unapproved-empty-case":
        packet.cases[2].dataset_labels_approved = None
    elif fault == "missing-judgement":
        packet.cases[0].judgements.clear()
    elif fault == "pending":
        packet.review_status = "pending"
    else:
        run.cases[0].proposals[0].content = "Changed after accepted review."
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        review.score_review(dataset, digest, run, packet, execution_telemetry=decoded(sidecar()))


def test_review_cli_consumes_sidecar_and_keeps_human_quality_gate_pending(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "review",
            "--split",
            "tuning",
            "--run",
            str(ROOT / f"{SEQUENTIAL}.json"),
            "--review",
            str(REVIEWS / f"{SEQUENTIAL}.review-completed.json"),
            "--telemetry",
            str(ROOT / f"{SEQUENTIAL}.telemetry.json"),
        ],
    )
    assert review.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["execution"]["case_counts"]["attempted_failed_network_cases"] == 1
    assert report["execution"]["case_counts"]["unattempted_cases"] == 9
    assert report["rates"]["useful_claim_recall"] == 0.1
    assert report["quality_gate"] == "pending"


def test_evaluate_cli_validates_sidecar_without_authentication_or_provider_calls(
    tmp_path, monkeypatch, capsys
):
    dataset, digest, run, packet = bundle()
    annotations = evaluate.Annotations(
        schema_version=1,
        label_source="human_reviewed",
        dataset_sha256=digest,
        run_sha256=packet.run_sha256,
        cases=[
            evaluate.AnnotatedCase(
                case_id=case.case_id,
                judgements=[evaluate.Judgement(**item.model_dump()) for item in case.judgements],
            )
            for case in packet.cases
        ],
    )
    annotations_path, telemetry_path = tmp_path / "annotations.json", tmp_path / "telemetry.json"
    annotations_path.write_text(annotations.model_dump_json(), encoding="utf-8")
    telemetry_path.write_text(json.dumps(sidecar()), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate",
            "--run",
            str(ROOT / f"{SEQUENTIAL}.json"),
            "--annotations",
            str(annotations_path),
            "--telemetry",
            str(telemetry_path),
        ],
    )
    assert evaluate.main() == 0
    assert json.loads(capsys.readouterr().out)["execution"]["case_counts"]["unattempted_cases"] == 9
    telemetry_path.write_text(json.dumps(malformed(sidecar(), "run-hash")), encoding="utf-8")
    assert evaluate.main() == 1
    assert json.loads(capsys.readouterr().out) == {"error": "INVALID_INPUT"}


def test_review_preparation_validates_sidecar_but_leaves_all_human_fields_blank(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "new-review.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "review",
            "--split",
            "tuning",
            "--run",
            str(ROOT / f"{SEQUENTIAL}.json"),
            "--prepare",
            "--output",
            str(output),
            "--telemetry",
            str(ROOT / f"{SEQUENTIAL}.telemetry.json"),
        ],
    )
    assert review.main() == 0
    packet = json.loads(output.read_text(encoding="utf-8"))
    assert packet["review_status"] == "pending"
    assert packet["reviewer"] is None
    assert all(case["dataset_labels_approved"] is None for case in packet["cases"])
    assert '"execution": "provider_stop"' in output.with_suffix(".md").read_text(encoding="utf-8")
    assert json.loads(capsys.readouterr().out)["model_called"] is False
