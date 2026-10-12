"""Reusable quota client tests use mock HTTP and no live requests."""

from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.bounded import QuotaClient
from contextbridge.formation.providers.chat import VerificationResponse
from contextbridge.formation.providers.quota import TokenGate
from tests.formation.test_groq_provider import Clock, settings


def test_shared_quota_and_call_budget_serialize_two_clients_before_http():
    clock, calls, requests = Clock(), [], []
    gate = TokenGate(clock=clock.clock, sleeper=clock.sleep, smooth=True)

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"support":"supported"}'},
                    }
                ],
            },
        )

    clients = [
        QuotaClient(settings(), calls, 1, gate=gate, transport=httpx.MockTransport(handler))
        for _ in range(2)
    ]

    def execute(client):
        try:
            return client.complete(
                client.settings.model, "Check synthetic support", {}, VerificationResponse
            )
        except ModuleError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(execute, clients))
    assert len(requests) == len(calls) == 1
    assert results.count("CANCELLED") == 1
    assert calls[0]["observation"].cost_usd is None


@pytest.mark.parametrize("limit", [0, 41, True])
def test_invalid_call_budget_rejected_before_transport(limit):
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        QuotaClient(settings(), max_calls=limit)
