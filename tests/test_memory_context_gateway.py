import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from contextbridge.mcp_adapter.arguments import ContextArguments
from contextbridge.mcp_adapter.gateway import GatewayError, MemoryGateway
from tests.test_mcp_adapter import settings


@pytest.mark.parametrize(
    "mutation",
    ["none", "project", "conditions", "historical_current", "stale", "duplicate", "forged_edge"],
)
def test_context_gateway_binds_query_and_rejects_forged_context(mutation):
    memory_id, seed_id, old_id = str(uuid4()), str(uuid4()), str(uuid4())
    now = datetime.now(UTC)
    base = {
        "memory_id": memory_id,
        "type": "FACT",
        "scope": "project",
        "project_id": "project-a",
        "conditions": {},
        "decision_state": "clear",
        "verification": "not_requested",
        "source_ref": {"agent": "test", "session": "session", "interaction": "turn"},
    }

    def handle(request):
        sent = json.loads(request.content)
        assert request.url.path == "/v1/retrieval/context"
        assert sent["project_id"] == "project-a" and not sent["verify_conflicts"]
        seed = base | {
            "version_id": seed_id,
            "version_number": 2,
            "content": "Use SQLite.",
            "role": "seed",
            "relation": None,
            "status": "ACTIVE",
            "applicable_at_query": True,
            "valid_from": (now - timedelta(days=1)).isoformat(),
            "valid_to": None,
        }
        old = base | {
            "version_id": old_id,
            "version_number": 1,
            "content": "Use PostgreSQL.",
            "role": "historical",
            "relation": "supersedes",
            "status": "SUPERSEDED",
            "applicable_at_query": False,
            "valid_from": (now - timedelta(days=3)).isoformat(),
            "valid_to": (now - timedelta(days=1)).isoformat(),
            "edge_source_version_id": seed_id,
            "edge_target_version_id": old_id,
        }
        if mutation == "project":
            old["project_id"] = "other-project"
        elif mutation == "conditions":
            old["conditions"] = {"environment": "production"}
        elif mutation == "historical_current":
            old["applicable_at_query"] = True
        elif mutation == "stale":
            seed["version_number"] = 3
        elif mutation == "duplicate":
            old["version_id"] = seed_id
        elif mutation == "forged_edge":
            old["edge_source_version_id"] = str(uuid4())
        return httpx.Response(
            200, json={"as_of": sent["as_of"], "items": [seed, old], "warnings": []}
        )

    async def run():
        gateway = MemoryGateway(settings(), httpx.MockTransport(handle))
        args = ContextArguments(memory_id=memory_id, expected_version=2)
        if mutation == "none":
            result = await gateway.context(args)
            assert result["items"][1]["applicable_at_query"] is False
        else:
            with pytest.raises(GatewayError):
                await gateway.context(args)

    asyncio.run(run())
