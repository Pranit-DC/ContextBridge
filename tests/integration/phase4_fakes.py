"""Synthetic HTTP responses through the current hosted assembly; never live credentials."""

import json
from datetime import UTC, datetime, timedelta

import httpx

from contextbridge.db import make_session_factory
from contextbridge.persistence.provider_quota import AccountGate
from contextbridge.runtime import assemble, hosted_backends
from scripts.v1.budget import BudgetTransport, Ledger
from tests.formation.test_groq_provider import settings as formation_settings
from tests.formation.test_grounded_provider import check, wire


class HostedReplay:
    def __init__(self, harness, monkeypatch, tmp_path, respond):
        self.requests = []
        self.ledger_path = tmp_path / "offline-request-ledger.sqlite"
        self.clock = datetime.now(UTC)
        sessions = make_session_factory(harness.database[1])

        def advance(seconds):
            self.clock += timedelta(seconds=seconds)

        def gate(*args, **kwargs):
            return AccountGate(
                *args, **(kwargs | {"clock": lambda: self.clock, "sleeper": advance})
            )

        monkeypatch.setattr(
            "contextbridge.formation.providers.config.load_settings", formation_settings
        )
        monkeypatch.setattr("contextbridge.persistence.provider_quota.AccountGate", gate)
        harness.settings = harness.settings.model_copy(update={"formation_enabled": True})
        self.backends = hosted_backends(harness.settings, sessions)

        def handle(request):
            body = json.loads(request.content)
            assert body["model"] == "openai/gpt-oss-120b"
            assert body["max_completion_tokens"] <= 1024
            assert body["response_format"]["json_schema"]["strict"] is True
            name = body["response_format"]["json_schema"]["name"]
            payload = json.loads(body["messages"][-1]["content"])
            self.requests.append((name, payload))
            value = respond(name, payload)
            if isinstance(value, httpx.Response):
                return value
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": json.dumps(value)},
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                },
            )

        for client in (
            self.backends.extraction_provider.client,
            self.backends.evidence_judge.client,
            self.backends.context_evidence_judge.client,
        ):
            client.transport = BudgetTransport(
                self.ledger_path, "groq", transport=httpx.MockTransport(handle)
            )
        self.providers = assemble(harness.settings, sessions, self.backends)

    def snapshot(self):
        return Ledger(self.ledger_path).snapshot()


def extraction_response(candidates, name, payload):
    """These outputs are test substitutes, not reviewed model judgements."""
    if name == "Claims":
        return {"claims": [wire(c) for c in candidates]}
    if name == "Checks":
        return {"checks": [check(c, index=i) for i, c in enumerate(candidates)]}
    raise AssertionError(f"Unexpected provider stage: {name}")
