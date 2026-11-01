"""Quota and CLI execution regressions use fixtures and an isolated OS lease."""

import json

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.quota import TokenGate
from scripts.formation import evaluate, verify_groq
from scripts.formation.execution import ExecutionTelemetry, summarize_execution
from tests.formation.test_groq_provider import Clock, settings


def install(monkeypatch, tmp_path, *, changes=None, envelope=None):
    clock = Clock()
    monkeypatch.setattr(verify_groq, "load_settings", lambda: settings(**(changes or {})))
    monkeypatch.setattr(
        verify_groq,
        "TokenGate",
        lambda **kw: TokenGate(clock=clock.clock, sleeper=clock.sleep, **kw),
    )
    lease = verify_groq.evaluation_lease
    monkeypatch.setattr(verify_groq, "evaluation_lease", lambda _: lease(tmp_path / "fixture.lock"))
    initialize = ChatClient.__init__

    def init(self, configured):
        initialize(
            self,
            configured,
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=envelope)),
        )

    monkeypatch.setattr(ChatClient, "__init__", init)
    return clock


def arguments(monkeypatch, path, *extra):
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify_groq",
            "--model",
            "openai/gpt-oss-120b",
            "--output",
            str(path),
            "--execute",
            "--confirm-free-plan",
            *extra,
        ],
    )


def exported(path):
    dataset, digest = evaluate.load_dataset("tuning")
    run = evaluate.decode(evaluate.Run, evaluate.read_payload(path))
    telemetry = evaluate.decode(
        ExecutionTelemetry, evaluate.read_payload(path.with_suffix(".telemetry.json"))
    )
    return summarize_execution(dataset, digest, run, telemetry), telemetry


def test_cli_exports_unknown_usage_and_completed_empty_network_cases(tmp_path, monkeypatch, capsys):
    path = tmp_path / "run.json"
    install(
        monkeypatch,
        tmp_path,
        envelope={
            "model": "openai/gpt-oss-120b",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"candidates":[]}'},
                }
            ],
        },
    )
    arguments(monkeypatch, path)
    assert verify_groq.main() == 0
    counts, telemetry = exported(path)
    assert 0 < len(telemetry.calls) < 11
    assert counts["case_counts"]["completed_network_cases"] == len(telemetry.calls)
    assert counts["case_counts"]["token_budget_cases"] == 11 - len(telemetry.calls)
    assert sum(call.reserved_tokens for call in telemetry.calls) <= 50000
    assert counts["case_counts"]["local_only_cases"] == 1
    assert all(call.input_tokens is None and call.cost_usd is None for call in telemetry.calls)
    assert all(call.reserved_tokens > 0 for call in telemetry.calls)
    assert "synthetic-groq-fixture-key" not in path.read_text()
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["quality_gate"] == "pending"


def test_cli_total_token_budget_stops_before_any_network_call(tmp_path, monkeypatch):
    path = tmp_path / "run.json"
    install(monkeypatch, tmp_path)
    monkeypatch.setattr(ChatClient, "complete", lambda *_: pytest.fail("Budget must stop locally"))
    arguments(monkeypatch, path, "--max-total-tokens", "128")
    assert verify_groq.main() == 0
    summary, telemetry = exported(path)
    assert not telemetry.calls
    assert summary["case_counts"]["token_budget_cases"] == 11
    assert summary["case_counts"]["local_only_cases"] == 1


def test_token_budget_evidence_requires_a_real_budget_violation(tmp_path, monkeypatch):
    path = tmp_path / "run.json"
    install(monkeypatch, tmp_path)
    arguments(monkeypatch, path, "--max-total-tokens", "128")
    assert verify_groq.main() == 0
    data = json.loads(path.with_suffix(".telemetry.json").read_text())
    data["execution"]["max_total_tokens"] = 50000
    data["cases"][0]["required_tokens"] = 1
    parsed = evaluate.decode(ExecutionTelemetry, json.dumps(data).encode())
    dataset, digest = evaluate.load_dataset("tuning")
    run = evaluate.decode(evaluate.Run, evaluate.read_payload(path))
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        summarize_execution(dataset, digest, run, parsed)


def test_paid_opt_in_and_unapproved_holdout_rejected_before_transport(tmp_path, monkeypatch):
    path = tmp_path / "run.json"
    install(monkeypatch, tmp_path, changes={"allow_paid": True})
    monkeypatch.setattr(ChatClient, "complete", lambda *_: pytest.fail("No paid call"))
    arguments(monkeypatch, path)
    assert verify_groq.main() == 1 and not path.exists()
    monkeypatch.setattr(verify_groq, "load_settings", settings)
    arguments(monkeypatch, path, "--split", "holdout")
    assert verify_groq.main() == 1 and not path.exists()


def test_safe_machine_error_code_excludes_raw_error_and_key(monkeypatch):
    from contextbridge.formation.providers.chat import VerificationResponse
    from tests.formation.test_groq_provider import KEY

    client = ChatClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                400,
                json={
                    "error": {
                        "code": "json_validate_failed",
                        "message": KEY + " private rejected content",
                    }
                },
            )
        ),
    )
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE"):
        client.complete(client.settings.model, "Synthetic prompt", {}, VerificationResponse)
    assert client.last_observation.provider_error_code == "json_validate_failed"
    assert KEY not in repr(client.last_observation)


@pytest.mark.parametrize(
    "code", ["unknown_raw_error", "gsk_secret_should_not_escape", {"content": "raw"}]
)
def test_unknown_or_nontext_error_codes_are_discarded(code):
    from contextbridge.formation.providers.chat import VerificationResponse

    client = ChatClient(
        settings(),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(400, json={"error": {"code": code}})
        ),
    )
    with pytest.raises(ModuleError):
        client.complete(client.settings.model, "Synthetic prompt", {}, VerificationResponse)
    assert client.last_observation.provider_error_code is None
