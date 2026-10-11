import copy
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import ChatClient, ChatEvidenceVerifier, Observation
from contextbridge.formation.providers.config import FormationSettings
from scripts.formation import verify_free as runner
from scripts.formation.evaluate import fixture_candidate, load_dataset


def settings():
    return FormationSettings(
        _env_file=None,
        provider="openrouter",
        model="apodex/apodex-1.1-mini:free",
        api_key="synthetic-verification-key-12345",
        allow_hosted=True,
        response_format="json_object",
    )


def test_call_budget_blocks_execution_before_transport(monkeypatch):
    executed = []
    monkeypatch.setattr(
        ChatClient, "complete", lambda *args: executed.append(args) or '{"candidates":[]}'
    )
    calls = []
    first = runner.BoundedClient(settings(), calls, 1)
    second = runner.BoundedClient(settings(), calls, 1)
    first.complete("example/model:free", "prompt", {}, object)
    with pytest.raises(ModuleError, match="CANCELLED"):
        second.complete("example/model:free", "prompt", {}, object)
    assert len(executed) == len(calls) == 1


def test_verdict_reuse_requires_identical_candidate_and_event(monkeypatch):
    observed = []
    monkeypatch.setattr(
        ChatEvidenceVerifier,
        "verify",
        lambda self, candidate, event: observed.append((candidate, event)) or "supported",
    )
    verifier = runner.OnceVerifier(ChatClient(settings()))
    candidate, event = {"content": "first claim"}, {"messages": ["first evidence"]}
    assert verifier.verify(candidate, event) == "supported"
    assert verifier.verify(copy.deepcopy(candidate), copy.deepcopy(event)) == "supported"
    verifier.verify({"content": "other claim"}, event)
    verifier.verify(candidate, {"messages": ["changed evidence"]})
    assert len(observed) == 3


def test_semantic_rejection_preserves_untrusted_proposal_without_admission(monkeypatch):
    dataset, _ = load_dataset("tuning")
    case = dataset.cases[0]
    candidate = fixture_candidate(case, case.expected_claims[0]).model_dump(mode="json")
    monkeypatch.setattr(runner.ChatModelProvider, "generate", lambda *args: json.dumps([candidate]))
    monkeypatch.setattr(runner.ChatEvidenceVerifier, "verify", lambda *args: "unsupported")
    predictions, calls = runner.measure(SimpleNamespace(cases=[case]), settings(), 1)
    assert predictions[0].proposals[0].model_dump(mode="json") == candidate
    assert predictions[0].error_code == "INVALID_PROVIDER_OUTPUT"
    assert predictions[0].decisions == []
    assert predictions[0].cost is None
    assert predictions[0].latency_ms is None
    assert calls == 0


def test_runner_refuses_overwrite_before_any_model_call(tmp_path, monkeypatch, capsys):
    output = tmp_path / "existing.json"
    output.write_text("preserved", encoding="utf-8")
    monkeypatch.setattr(runner, "load_settings", settings)
    monkeypatch.setattr(runner, "measure", lambda *args: pytest.fail("Existing run must survive"))
    monkeypatch.setattr(
        "sys.argv", ["verify_free.py", "--split", "tuning", "--output", str(output), "--execute"]
    )
    assert runner.main() == 1
    assert output.read_text(encoding="utf-8") == "preserved"
    assert "synthetic-verification-key" not in capsys.readouterr().out


def test_telemetry_preserves_requested_and_actual_models_for_failed_output(monkeypatch):
    dataset, _ = load_dataset("tuning")
    case = dataset.cases[0]

    def malformed(self, *args):
        self.last_observation = Observation("example/actual-model", 0.2, 12, 6, 0)
        raise ModuleError("INVALID_PROVIDER_OUTPUT")

    monkeypatch.setattr(ChatClient, "complete", malformed)
    telemetry = []
    predictions, calls = runner.measure(
        SimpleNamespace(cases=[case]), settings(), 1, telemetry=telemetry
    )
    assert calls == 1
    assert predictions[0].error_code == "INVALID_PROVIDER_OUTPUT"
    assert predictions[0].input_tokens == 12
    assert predictions[0].cost == 0
    assert telemetry[0]["case_id"] == case.case_id
    assert telemetry[0]["stage"] == "extraction"
    assert telemetry[0]["requested_model"] == "apodex/apodex-1.1-mini:free"
    assert telemetry[0]["observed_model"] == "example/actual-model"
    assert telemetry[0]["error_code"] == "INVALID_PROVIDER_OUTPUT"
    assert telemetry[0]["latency_ms"] >= 0
    assert "synthetic-verification-key" not in json.dumps(telemetry)


def test_failed_transport_has_unknown_usage_and_model(monkeypatch):
    def unavailable(*args):
        raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True)

    monkeypatch.setattr(ChatClient, "complete", unavailable)
    client = runner.BoundedClient(settings(), [], 1)
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE"):
        client.complete("example/model:free", "prompt", {}, object)
    assert client.calls[0]["observation"] is None
    assert client.calls[0]["retryable"] is True
    assert client.calls[0]["latency_ms"] >= 0


def test_existing_telemetry_is_preserved_before_execution(tmp_path, monkeypatch):
    output = tmp_path / "new-run.json"
    telemetry = output.with_suffix(".telemetry.json")
    telemetry.write_text("preserved", encoding="utf-8")
    monkeypatch.setattr(runner, "load_settings", settings)
    monkeypatch.setattr(runner, "measure", lambda *args: pytest.fail("No model call allowed"))
    monkeypatch.setattr(
        "sys.argv", ["verify_free.py", "--split", "tuning", "--output", str(output), "--execute"]
    )
    assert runner.main() == 1
    assert telemetry.read_text(encoding="utf-8") == "preserved"
    assert not output.exists()


def test_spacing_is_shared_between_extraction_and_verification(monkeypatch):
    now, starts, sleeps = [0.0], [], []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    def complete(*args):
        starts.append(now[0])
        now[0] += 1
        return '{"candidates":[]}'

    monkeypatch.setattr(ChatClient, "complete", complete)
    gate = runner.RequestGate(3.1, clock=lambda: now[0], sleeper=sleep)
    calls = []
    extraction = runner.BoundedClient(settings(), calls, 3, gate=gate)
    verification = runner.BoundedClient(settings(), calls, 3, gate=gate, stage="verification")
    for client in (extraction, verification, extraction):
        client.complete(settings().model, "prompt", {}, object)
    assert starts == pytest.approx([0, 3.1, 6.2])
    assert sleeps == pytest.approx([2.1, 2.1])
    assert [call["stage"] for call in calls] == ["extraction", "verification", "extraction"]


def test_shared_gate_serializes_attempts_and_checks_budget_inside_lock(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    starts = []

    def complete(*args):
        starts.append(1)
        entered.set()
        assert release.wait(5)
        return '{"candidates":[]}'

    monkeypatch.setattr(ChatClient, "complete", complete)
    calls, gate = [], runner.RequestGate(0)
    clients = [runner.BoundedClient(settings(), calls, 1, gate=gate) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(clients[0].complete, settings().model, "prompt", {}, object)
        assert entered.wait(5)
        second = pool.submit(clients[1].complete, settings().model, "prompt", {}, object)
        assert starts == [1]
        release.set()
        assert first.result(timeout=5) == '{"candidates":[]}'
        with pytest.raises(ModuleError, match="CANCELLED"):
            second.result(timeout=5)
    assert starts == [1]
    assert len(calls) == 1


@pytest.mark.parametrize("retryable", [True, False])
def test_provider_failure_stops_later_calls_without_hiding_unexecuted_cases(monkeypatch, retryable):
    dataset, _ = load_dataset("tuning")
    cases = [dataset.cases[0], dataset.cases[1]]
    assistant = next(case for case in dataset.cases if case.category == "assistant-suggestion")

    def unavailable(self, *args):
        self.last_observation = Observation(None, 0.1, None, None, None, 429 if retryable else 401)
        raise ModuleError("PROVIDER_UNAVAILABLE", retryable=retryable)

    monkeypatch.setattr(ChatClient, "complete", unavailable)
    telemetry, case_telemetry = [], []
    predictions, calls = runner.measure(
        SimpleNamespace(cases=[*cases, assistant]),
        settings(),
        10,
        telemetry=telemetry,
        case_telemetry=case_telemetry,
        gate=runner.RequestGate(0),
    )
    assert calls == 1
    assert [case["execution"] for case in case_telemetry] == [
        "attempted",
        "provider_stop",
        "local_only",
    ]
    assert predictions[1].latency_ms is None
    assert predictions[1].cost is None
    assert predictions[1].error_code == "PROVIDER_UNAVAILABLE"
    assert predictions[2].error_code is None
    assert telemetry[0]["http_status"] == (429 if retryable else 401)


def test_malformed_output_does_not_stop_other_cases_or_retry_same_case(monkeypatch):
    dataset, _ = load_dataset("tuning")
    attempts = []

    def malformed(self, model, prompt, payload, schema):
        attempts.append(payload["event_id"])
        raise ModuleError("INVALID_PROVIDER_OUTPUT")

    monkeypatch.setattr(ChatClient, "complete", malformed)
    predictions, calls = runner.measure(
        SimpleNamespace(cases=dataset.cases[:2]), settings(), 4, gate=runner.RequestGate(0)
    )
    assert calls == 2
    assert len(set(attempts)) == 2
    assert all(case.error_code == "INVALID_PROVIDER_OUTPUT" for case in predictions)


def test_evaluation_lease_blocks_another_process_and_releases_after_failure(tmp_path):
    path = tmp_path / "evaluation.lock"
    code = (
        "from pathlib import Path; from scripts.formation.verify_free import evaluation_lease; "
        "with_lease = evaluation_lease(Path(__import__('sys').argv[1])); "
        "with_lease.__enter__(); with_lease.__exit__(None, None, None)"
    )
    with pytest.raises(RuntimeError):
        with runner.evaluation_lease(path):
            result = subprocess.run(
                [sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=15
            )
            assert result.returncode != 0
            assert "CANCELLED" in result.stderr
            raise RuntimeError("synthetic crash")
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("interval", ["0", "3", "61", "nan", "inf"])
def test_cli_rejects_unsafe_spacing_before_any_model_call(tmp_path, monkeypatch, interval):
    monkeypatch.setattr(runner, "load_settings", settings)
    monkeypatch.setattr(runner, "measure", lambda *args, **kwargs: pytest.fail("No model call"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_free.py",
            "--split",
            "tuning",
            "--output",
            str(tmp_path / "run.json"),
            "--execute",
            "--request-interval",
            interval,
        ],
    )
    assert runner.main() == 1


def test_cli_exports_hash_bound_execution_and_call_metadata(tmp_path, monkeypatch):
    output = tmp_path / "run.json"
    monkeypatch.setattr(runner, "load_settings", settings)

    def malformed(self, *args):
        self.last_observation = Observation("apodex/apodex-1.1-mini", 0.1, 12, 4, 0, 200)
        raise ModuleError("INVALID_PROVIDER_OUTPUT")

    monkeypatch.setattr(ChatClient, "complete", malformed)
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_free.py",
            "--split",
            "tuning",
            "--output",
            str(output),
            "--execute",
            "--max-calls",
            "1",
        ],
    )
    assert runner.main() == 0
    exported = json.loads(output.read_text(encoding="utf-8"))
    telemetry = json.loads(output.with_suffix(".telemetry.json").read_text(encoding="utf-8"))
    from scripts.formation.evaluate import Run, dataset_digest

    assert telemetry["run_sha256"] == dataset_digest(Run.model_validate(exported))
    assert telemetry["execution"]["concurrency"] == 1
    assert telemetry["execution"]["automatic_retries"] == 0
    assert telemetry["calls"][0]["http_status"] == 200
    assert telemetry["cases"][1]["execution"] == "call_budget"
    assert settings().api_key.get_secret_value() not in json.dumps([exported, telemetry])
