"""Offline synthetic CLI regressions, never live-model quality measurements."""

import json

import httpx
import pytest

from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.quota import TokenGate
from scripts.formation import verify_consolidation
from scripts.formation.demo_consolidation import load_cases
from tests.formation.test_groq_provider import KEY, Clock, settings


def configure(monkeypatch, tmp_path, *, changes=None, failure=False):
    clock, requests = Clock(), []
    monkeypatch.setattr(verify_consolidation, "load_settings", lambda: settings(**(changes or {})))
    monkeypatch.setattr(
        verify_consolidation,
        "TokenGate",
        lambda **kw: TokenGate(clock=clock.clock, sleeper=clock.sleep, **kw),
    )
    lease = verify_consolidation.evaluation_lease
    monkeypatch.setattr(
        verify_consolidation, "evaluation_lease", lambda _: lease(tmp_path / "fixture.lock")
    )
    initialize = ChatClient.__init__

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "openai/gpt-oss-120b"
        if failure:
            return httpx.Response(
                429, json={"error": {"code": "rate_limit_exceeded", "message": KEY}}
            )
        payload = json.loads(body["messages"][1]["content"])
        value = {"groups": []} if "proposal" not in payload else {"support": "supported"}
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(value)},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    monkeypatch.setattr(
        ChatClient,
        "__init__",
        lambda self, configured: initialize(
            self, configured, transport=httpx.MockTransport(handler)
        ),
    )
    return requests


def args(monkeypatch, output, *extra, consent=True):
    argv = ["verify_consolidation", "--output", str(output)]
    if consent:
        argv += ["--execute", "--confirm-free-plan"]
    monkeypatch.setattr("sys.argv", argv + list(extra))


def test_export_retains_all_cases_and_unknown_cost_without_persistence(monkeypatch, tmp_path):
    requests = configure(monkeypatch, tmp_path)
    output = tmp_path / "run.json"
    args(monkeypatch, output)
    assert verify_consolidation.main() == 0
    saved = json.loads(output.read_text())
    assert {c["case_id"] for c in saved["cases"]} == {c["id"] for c in load_cases()}
    assert requests and len(requests) == len(saved["calls"])
    assert all(c["proposals"] == [] for c in saved["cases"])
    assert all(c["execution"] in ("attempted", "local_only") for c in saved["cases"])
    assert all(c["cost_usd"] is None for c in saved["calls"])
    assert saved["quality_gate"] == "pending" and saved["memory_saved"] is False
    assert saved["label_status"] == "design_labels_independent_review_pending"
    assert KEY not in output.read_text()


def test_budget_exhaustion_is_not_a_failed_model_execution(monkeypatch, tmp_path):
    requests = configure(monkeypatch, tmp_path)
    output = tmp_path / "run.json"
    args(monkeypatch, output, "--max-total-tokens", "128")
    assert verify_consolidation.main() == 0
    saved = json.loads(output.read_text())
    assert requests == saved["calls"] == []
    blocked = [c for c in saved["cases"] if c["error_code"]]
    assert blocked and all(c["execution"] == "token_budget" for c in blocked)


def test_provider_failure_stops_later_calls_and_exports_only_safe_code(monkeypatch, tmp_path):
    requests = configure(monkeypatch, tmp_path, failure=True)
    output = tmp_path / "run.json"
    args(monkeypatch, output)
    assert verify_consolidation.main() == 0
    saved = json.loads(output.read_text())
    assert len(requests) == len(saved["calls"]) == 1
    assert saved["calls"][0]["http_status"] == 429
    assert saved["calls"][0]["provider_error_code"] == "rate_limit_exceeded"
    assert sum(c["execution"] == "attempted" for c in saved["cases"]) == 1
    assert any(c["execution"] == "provider_stop" for c in saved["cases"])
    assert KEY not in output.read_text()


@pytest.mark.parametrize("mode", ["consent", "paid", "endpoint", "overwrite", "directory"])
def test_execution_gates_fail_before_any_call(monkeypatch, tmp_path, mode):
    changes = (
        {"allow_paid": True}
        if mode == "paid"
        else {"base_url": "https://different-provider.example/v1"}
        if mode == "endpoint"
        else None
    )
    requests = configure(monkeypatch, tmp_path, changes=changes)
    output = tmp_path / "run.json"
    if mode == "overwrite":
        output.write_text("retain-existing-artifact")
    if mode == "directory":
        output = tmp_path / "absent" / "run.json"
    args(monkeypatch, output, consent=mode != "consent")
    assert verify_consolidation.main() == 1
    assert requests == []
    if mode == "overwrite":
        assert output.read_text() == "retain-existing-artifact"
