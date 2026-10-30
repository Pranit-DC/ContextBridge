import asyncio
import json
from uuid import uuid4

import httpx
import pytest
from mcp import Client

from contextbridge.capture_adapters import cli
from contextbridge.engine.errors import ModuleError
from contextbridge.evidence_time.client import BundleClient
from contextbridge.mcp_adapter.gateway import MemoryGateway
from contextbridge.mcp_adapter.server import create_server
from tests.integration.test_evidence_time import bundle
from tests.test_mcp_adapter import TOKEN, memory, settings


def payload():
    value = bundle()
    for event in value["events"]:
        event["project_id"] = "project-a"
    return value


def test_bundle_cli_validates_without_network_or_exposing_quotes(tmp_path, monkeypatch, capsys):
    value = payload()
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TOKEN)
    monkeypatch.setattr(
        "sys.argv",
        ["contextbridge-import", "--project-id", "project-a", "validate-bundle", str(path)],
    )
    assert cli.main() == 0
    output = capsys.readouterr()
    data = json.loads(output.out)
    assert data["bundle_id"] == value["bundle_id"] and data["event_count"] == 2
    assert "SQLite" not in output.out and TOKEN not in output.out


def test_bundle_client_preserves_source_offsets_and_does_not_retry_lost_response():
    value = payload()
    calls = []

    def handle(request):
        assert request.url.path == "/v2/interactions/bundles"
        calls.append(json.loads(request.content))
        raise httpx.ReadTimeout(TOKEN)

    client = BundleClient(settings(), transport=httpx.MockTransport(handle))
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE"):
        client.submit(value)
    assert len(calls) == 1
    assert calls[0]["events"][0]["occurred_at"] == value["events"][0]["occurred_at"]
    value["events"][0]["project_id"] = "another"
    with pytest.raises(ModuleError):
        client.submit(value)
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["auto", "legacy"])
@pytest.mark.parametrize("bad", [None, "project", "conditions", "version", "id", "warning"])
def test_mcp_temporal_context_guards_and_provenance(mode, bad):
    row = memory()
    at = row["version"]["valid_from"]
    response = {
        "schema_version": 2,
        "as_of": at,
        "items": [
            {
                "memory": row,
                "decision_state": "clear",
                "role": "applicable_at_time",
                "applicability": "applicable",
                "temporal": None,
            }
        ],
        "warnings": [],
    }
    identifier = row["id"]
    if bad == "project":
        row["project_id"] = "other"
    if bad == "conditions":
        row["conditions"] = {"environment": "production"}
    if bad == "version":
        row["current_version"] = 2
    if bad == "id":
        row["id"] = str(uuid4())
    if bad == "warning":
        response["warnings"] = ["private-provider-output"]

    def handle(request):
        body = json.loads(request.content)
        assert body["project_id"] == "project-a"
        if request.url.path.endswith("provenance"):
            return httpx.Response(
                200,
                json={
                    "scope": "project",
                    "project_id": "project-a",
                    "memory_id": identifier,
                    "version": 1,
                    "metadata": {"schema_version": 1, "precision": "instant"},
                },
            )
        assert request.url.path.endswith("temporal-context")
        return httpx.Response(200, json=response)

    async def scenario():
        gateway = MemoryGateway(settings(), httpx.MockTransport(handle))
        async with Client(create_server(gateway), mode=mode) as client:
            result = await client.call_tool(
                "memory_temporal_context",
                {"memory_id": identifier, "expected_version": 1, "as_of": at},
            )
            assert result.is_error == bool(bad)
            provenance = await client.call_tool(
                "memory_provenance", {"memory_id": identifier, "version": 1}
            )
            assert not provenance.is_error
            assert provenance.structured_content["metadata"]["schema_version"] == 1

    asyncio.run(scenario())
