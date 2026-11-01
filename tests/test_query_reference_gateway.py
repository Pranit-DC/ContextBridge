import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from contextbridge.mcp_adapter.arguments import FollowupArguments
from contextbridge.mcp_adapter.gateway import GatewayError, MemoryGateway
from tests.test_mcp_adapter import memory, settings


@pytest.mark.parametrize("defect", ["none", "project", "scope", "limit"])
def test_gateway_binds_followup_and_applies_ordinary_card_guards(defect):
    from contextbridge.contracts import MemoryCard

    row = memory()
    version = row["version"]
    card = MemoryCard(
        memory_id=row["id"],
        version_id=version["id"],
        version_number=1,
        type=row["type"],
        content=version["content"],
        scope=row["scope"],
        project_id=row["project_id"],
        conditions={},
        valid_from=version["valid_from"],
        valid_to=None,
        decision_state="clear",
        verification="not_requested",
        source_ref={k: version["source"][k] for k in ["agent", "session", "interaction"]},
    ).model_dump(mode="json")
    identifier = str(uuid4())

    def handle(request):
        body = json.loads(request.content)
        assert request.url.path == "/v1/retrieval/referenced-search"
        assert body["memory_id"] == identifier and body["expected_version"] == 1
        assert body["query"]["project_id"] == "project-a" and body["query"]["query"] == "it"
        assert "memory_id" not in body["query"]
        if defect == "project":
            card["project_id"] = "elsewhere"
        if defect == "scope":
            card.update(scope="developer", project_id=None)
        return httpx.Response(
            200,
            json={
                "schema_version": 1,
                "cards": [card] * (2 if defect == "limit" else 1),
                "degraded": False,
                "warnings": ["SYNTHETIC_WARNING"],
            },
        )

    gateway = MemoryGateway(settings(), httpx.MockTransport(handle))
    args = FollowupArguments(query="it", memory_id=identifier, expected_version=1, limit=1)
    if defect == "none":
        result = asyncio.run(gateway.followup(args))
        assert result["warnings"] == ["SYNTHETIC_WARNING"] and len(result["cards"]) == 1
    else:
        with pytest.raises(GatewayError):
            asyncio.run(gateway.followup(args))
