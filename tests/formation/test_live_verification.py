import copy
import json
from types import SimpleNamespace

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import ChatClient, ChatEvidenceVerifier
from contextbridge.formation.providers.config import FormationSettings
from scripts.formation import verify_free as runner
from scripts.formation.evaluate import fixture_candidate, load_dataset


def settings():
    return FormationSettings(
        _env_file=None,
        provider="openrouter",
        model="example/model:free",
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
