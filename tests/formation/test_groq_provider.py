"""Groq protocol/quota fixtures; never measured model quality or live network calls."""

import copy
import json
from math import inf, nextafter

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import ChatClient, ChatModelProvider
from contextbridge.formation.providers.config import (
    GROQ_ENDPOINT,
    GROQ_FREE_MODELS,
    FormationSettings,
)
from contextbridge.formation.providers.quota import TokenGate

KEY = "synthetic-groq-fixture-key-12345"


def settings(**changes):
    return FormationSettings(
        _env_file=None,
        **(
            {
                "provider": "openai-compatible",
                "base_url": GROQ_ENDPOINT,
                "model": "openai/gpt-oss-120b",
                "api_key": KEY,
                "allow_hosted": True,
                "allow_paid": False,
                "groq_free_plan_confirmed": True,
                "max_output_tokens": 2048,
            }
            | changes
        ),
    )


@pytest.mark.parametrize("model", sorted(GROQ_FREE_MODELS))
def test_supported_models_use_strict_schema_without_router_or_paid_flags(model, event, candidate):
    def handle(request):
        assert str(request.url) == GROQ_ENDPOINT + "/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == model
        assert body["max_completion_tokens"] == 2048
        assert "max_tokens" not in body
        assert "provider" not in body
        assert body["include_reasoning"] is False
        assert body["reasoning_effort"] == "low"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert KEY not in request.content.decode()
        proposed = copy.deepcopy(candidate)
        proposed["conditions"] = [{"key": k, "value": v} for k, v in proposed["conditions"].items()]
        return httpx.Response(
            200,
            json={
                "model": model,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"candidates": [proposed]}),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 456, "cost": 0},
            },
        )

    client = ChatClient(settings(model=model), transport=httpx.MockTransport(handle))
    assert json.loads(ChatModelProvider(client).generate(event)) == [candidate]
    assert client.last_observation.input_tokens == 123
    assert client.last_observation.cost_usd is None
    assert KEY not in json.dumps(client.settings.public_configuration())


@pytest.mark.parametrize(
    "changes",
    [
        {"groq_free_plan_confirmed": False},
        {"allow_hosted": False},
        {"base_url": "https://other.example/v1"},
        {"model": "unapproved/model"},
        {"verifier_model": "unapproved/verifier"},
    ],
)
def test_missing_attestation_endpoint_mismatch_or_model_mismatch_blocks_execution(changes):
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        settings(**changes).check_execution()


class Clock:
    def __init__(self):
        self.now = 0
        self.waits = []

    def clock(self):
        return self.now

    def sleep(self, value):
        self.waits.append(value)
        # A monotonic clock advances after any positive sleep, even when a tiny
        # floating-point remainder would round self.now + value back to self.now.
        self.now = max(self.now + value, nextafter(self.now, inf)) if value > 0 else self.now


def gate(**changes):
    clock = Clock()
    return TokenGate(clock=clock.clock, sleeper=clock.sleep, **changes), clock


def test_reserved_tokens_wait_for_window_and_unknown_usage_is_not_zero():
    quota, clock = gate()
    quota.pending_tokens = 6000
    quota.wait()
    quota.observe(None)
    quota.pending_tokens = 3000
    quota.wait()
    assert clock.now == 61
    assert quota.total == 9000


def test_observed_usage_releases_unused_reservation_but_still_spaces_requests():
    from types import SimpleNamespace

    quota, clock = gate()
    quota.pending_tokens = 6000
    quota.wait()
    quota.observe(SimpleNamespace(input_tokens=1000, output_tokens=500))
    quota.pending_tokens = 4000
    quota.wait()
    assert clock.now == 3.1
    assert quota.total == 5500


@pytest.mark.parametrize("amount,budget", [(8001, 50000), (6000, 5000)])
def test_large_request_or_total_budget_exhaustion_stops_before_network(amount, budget):
    quota, clock = gate(max_total_tokens=budget)
    quota.pending_tokens = amount
    with pytest.raises(ModuleError, match="CANCELLED"):
        quota.wait()
    assert quota.token_stopped and quota.required_tokens == amount
    assert not clock.waits and quota.total == 0


def test_provider_failure_stops_without_waiting_or_reserving_more_tokens():
    quota, clock = gate()
    quota.pending_tokens = 1000
    quota.failure = True
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE"):
        quota.wait()
    assert quota.total == 0 and not clock.waits


@pytest.mark.parametrize(
    "changes",
    [
        {"tokens_per_minute": True},
        {"tokens_per_minute": 9000},
        {"max_total_tokens": 100000},
        {"interval": float("nan")},
    ],
)
def test_invalid_quota_parameters_rejected(changes):
    with pytest.raises(ValueError):
        gate(**changes)
