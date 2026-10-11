import json
import os
import sys

import httpx
import pytest
from pydantic import ValidationError

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.config import FormationSettings, load_settings
from scripts.formation import provider as runner

KEY = "synthetic-test-key-123456"


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    for key in list(os.environ):
        if key.upper().startswith("CONTEXTBRIDGE_FORMATION_"):
            monkeypatch.delenv(key)


def settings(**changes):
    values = {"provider": "openrouter", "model": "example/model:free", "api_key": KEY}
    return FormationSettings(_env_file=None, **(values | changes))


def test_local_file_and_environment_precedence(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        f"CONTEXTBRIDGE_FORMATION_PROVIDER=openrouter\n"
        f"CONTEXTBRIDGE_FORMATION_MODEL=example/file-model:free\n"
        f"CONTEXTBRIDGE_FORMATION_API_KEY={KEY}\n"
        "CONTEXTBRIDGE_API_TOKEN=unrelated-service-token\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_MODEL", "example/env-model:free")
    configured = load_settings(path)
    assert configured.model == "example/env-model:free"
    assert configured.api_key.get_secret_value() == KEY
    assert configured.base_url == "https://openrouter.ai/api/v1"
    assert configured.allow_hosted is False
    assert configured.allow_paid is False
    assert KEY not in repr(configured)
    assert KEY not in configured.model_dump_json()
    assert KEY not in json.dumps(configured.public_configuration())


def test_user_selects_loopback_provider_without_key():
    configured = settings(provider="ollama", model="user-model", api_key="")
    assert configured.base_url == "http://127.0.0.1:11434/v1"
    configured.check_execution()
    assert configured.public_configuration()["api_key_configured"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "unknown"},
        {"model": "example/paid-model"},
        {"verifier_model": "example/paid-verifier"},
        {"model": "openrouter/free"},
        {"api_key": None},
        {"api_key": "too-short"},
        {"api_key": KEY + "\r\nInjected: header"},
        {"model": KEY + ":free"},
        {"model": "sk-abcdefghijklmnopqrstuvwxyz:free"},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": 0},
        {"max_output_tokens": 999999},
        {"base_url": "https://unapproved.example/api/v1"},
        {"provider": "openai-compatible", "base_url": None},
        {"provider": "openai-compatible", "base_url": "http://remote.example/v1"},
        {"provider": "openai-compatible", "base_url": "https://user:password@api.example/v1"},
        {"provider": "openai-compatible", "base_url": "https://api.example/v1?token=value"},
        {"provider": "openai-compatible", "base_url": "https://api.example/v1#fragment"},
        {"provider": "openai-compatible", "base_url": "https://api.example:bad/v1"},
        {"provider": "openai-compatible", "base_url": "https://api.example/" + KEY},
        {"provider": "ollama", "base_url": "https://remote.example/v1"},
    ],
)
def test_bad_configuration_is_rejected_without_key_in_message(changes):
    with pytest.raises(ValidationError) as caught:
        settings(**changes)
    assert KEY not in str(caught.value)


def test_hosted_and_paid_execution_require_distinct_opt_ins():
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        settings().check_execution()
    settings(allow_hosted=True).check_execution()
    configured = settings(model="example/paid-model", openrouter_free_only=False, allow_hosted=True)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        configured.check_execution()
    settings(
        model="example/paid-model", openrouter_free_only=False, allow_hosted=True, allow_paid=True
    ).check_execution()
    compatible = settings(
        provider="openai-compatible", base_url="https://api.example/v1", allow_hosted=True
    )
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        compatible.check_execution()


def test_invalid_file_failure_is_sanitized(tmp_path):
    path = tmp_path / ".env"
    path.write_text(f"CONTEXTBRIDGE_FORMATION_PROVIDER={KEY}\n", encoding="utf-8")
    with pytest.raises(ModuleError) as caught:
        load_settings(path)
    assert str(caught.value) == "INVALID_INPUT"
    assert caught.value.__suppress_context__


def test_configuration_command_never_calls_network(tmp_path, monkeypatch, capsys):
    path = tmp_path / ".env"
    path.write_text(
        "CONTEXTBRIDGE_FORMATION_PROVIDER=openrouter\n"
        "CONTEXTBRIDGE_FORMATION_MODEL=example/model:free\n"
        f"CONTEXTBRIDGE_FORMATION_API_KEY={KEY}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["provider.py", "--env-file", str(path)])
    monkeypatch.setattr(httpx.Client, "stream", lambda *a, **kw: pytest.fail("No network allowed"))
    assert runner.main() == 0
    output = capsys.readouterr().out
    assert KEY not in output
    assert json.loads(output)["network_called"] is False


def test_unconfigured_command_fails_safely(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["provider.py", "--env-file", str(tmp_path / "absent")])
    assert runner.main() == 1
    assert json.loads(capsys.readouterr().out) == {"code": "INVALID_INPUT", "retryable": False}


def test_oversize_event_and_secret_event_fail_before_execution(tmp_path, event):
    path = tmp_path / "event.json"
    path.write_bytes(b" " * (runner.MAX_EVENT_BYTES + 1))
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        runner.read_event(path)
    event["messages"][0]["content"] = "api_key=private-token"
    path.write_text(json.dumps(event), encoding="utf-8")
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        runner.read_event(path)


def test_explicit_runner_execution_is_proposal_only_with_mock_http(
    tmp_path, monkeypatch, capsys, event, candidate
):
    import copy

    from contextbridge.formation.providers.chat import ChatClient

    config_file = tmp_path / ".env"
    config_file.write_text(
        "CONTEXTBRIDGE_FORMATION_PROVIDER=openrouter\n"
        "CONTEXTBRIDGE_FORMATION_MODEL=example/model:free\n"
        "CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED=true\n"
        f"CONTEXTBRIDGE_FORMATION_API_KEY={KEY}\n",
        encoding="utf-8",
    )
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps(event), encoding="utf-8")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if body["response_format"]["json_schema"]["name"] == "ExtractionResponse":
            proposed = copy.deepcopy(candidate)
            proposed["conditions"] = [
                {"key": key, "value": value} for key, value in candidate["conditions"].items()
            ]
            content = {"candidates": [proposed]}
        else:
            content = {"support": "supported"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(content)},
                    }
                ]
            },
        )

    monkeypatch.setattr(
        runner,
        "ChatClient",
        lambda configured: ChatClient(configured, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["provider.py", "--env-file", str(config_file), "--event", str(event_file), "--execute"],
    )
    assert runner.main() == 0
    output = capsys.readouterr().out
    assert KEY not in output
    result = json.loads(output)
    assert result["memory_saved"] is False
    assert result["quality_gate"] == "pending"
    assert result["comparison"] == "empty_snapshot_not_production"
    assert result["candidates"] == [candidate]
    assert result["decisions"][0]["outcome"] == "ADMIT"
    assert len(calls) == 3
