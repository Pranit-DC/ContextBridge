"""Actual shared-engine/PostgreSQL fencing through injected HTTP semantic adapters."""

import json

import httpx
import pytest
from sqlalchemy.orm import Session

from contextbridge.formation import Consolidator
from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.semantic import (
    ChatConsolidationVerifier,
    ChatGroupingProvider,
)
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.formation.test_consolidation_integration import process, setup
from tests.formation.test_groq_provider import settings as provider_settings

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "operation,phase",
    [
        ("none", "none"),
        ("update", "group"),
        ("update", "verify"),
        ("forget", "group"),
        ("forget", "verify"),
    ],
)
def test_real_adapter_path_obeys_engine_freshness_and_forget_fences(database, operation, phase):
    settings, sources, job = setup(database)
    calls = []

    def handler(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        stage = "group" if "proposal" not in payload else "verify"
        calls.append(stage)
        if operation != "none" and stage == phase:
            with Session(database[1]) as session:
                service = MemoryService(session, "developer-a")
                if operation == "forget":
                    service.forget(sources[0].id)
                else:
                    service.update(
                        sources[0].id,
                        UpdateMemory(
                            expected_version=1,
                            content="Use SQLite.",
                            source=sources[0].version.source,
                        ),
                    )
        value = (
            {"groups": [[r["memory"]["version"]["id"] for r in payload["records"]]]}
            if stage == "group"
            else {"support": "supported"}
        )
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
            },
        )

    client = ChatClient(provider_settings(), transport=httpx.MockTransport(handler))
    result = process(
        database,
        settings,
        job,
        Consolidator(ChatGroupingProvider(client), ChatConsolidationVerifier(client)),
    )
    expected = {"none": "succeeded", "update": "failed", "forget": "cancelled"}[operation]
    assert result["status"] == expected
    assert bool(result["memory_ids"]) == (operation == "none")
    if operation == "update":
        assert result["reason_codes"] == ["VERSION_CONFLICT"]
    assert calls
