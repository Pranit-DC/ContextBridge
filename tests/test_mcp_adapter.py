import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from mcp import Client
from pydantic import ValidationError

from contextbridge.mcp_adapter import cli
from contextbridge.mcp_adapter.arguments import NoArguments
from contextbridge.mcp_adapter.config import MCPSettings
from contextbridge.mcp_adapter.gateway import GatewayError, MemoryGateway
from contextbridge.mcp_adapter.server import create_server

TOKEN = "mcp-test-token-with-at-least-32-characters"


def settings(**changes):
    return MCPSettings(_env_file=None, api_token=TOKEN, project_id="project-a", **changes)


def write(**changes):
    return {
        "request_id": str(uuid4()),
        "type": "DECISION",
        "content": "Use PostgreSQL for project memory",
        "source": {
            "kind": "user",
            "interaction": "turn-1",
            "evidence": "The user explicitly chose PostgreSQL for project memory",
        },
        **changes,
    }


def memory(**changes):
    now = datetime.now(UTC).isoformat()
    return {
        "id": str(uuid4()),
        "scope": "project",
        "project_id": "project-a",
        "type": "DECISION",
        "conditions": {},
        "created_at": now,
        "current_version": 1,
        "version": {
            "id": str(uuid4()),
            "number": 1,
            "content": "Use PostgreSQL",
            "status": "ACTIVE",
            "valid_from": now,
            "valid_to": None,
            "recorded_at": now,
            "source": {
                **write()["source"],
                "agent": "codex",
                "session": "session-a",
            },
        },
        **changes,
    }


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://192.168.1.2:8000",
        "http://user:password@localhost:8000",
        "http://localhost:8000/api",
        "http://localhost:8000?token=secret",
        "http://localhost:8000#fragment",
    ],
)
def test_settings_reject_non_loopback_origins(url):
    with pytest.raises(ValidationError):
        settings(api_url=url)


@pytest.mark.parametrize("url", ["http://localhost:8000", "http://[::1]:8000"])
def test_settings_accept_local_origins(url):
    assert settings(api_url=url).api_url.host


def test_configuration_does_not_read_implicit_dotenv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CONTEXTBRIDGE_API_TOKEN", raising=False)
    (tmp_path / ".env").write_text(f"CONTEXTBRIDGE_API_TOKEN={TOKEN}\n")
    with pytest.raises(ValidationError):
        MCPSettings(project_id="example")
    assert MCPSettings(_env_file=tmp_path / ".env", project_id="example").api_token


def test_cli_configuration_errors_never_echo_inputs(monkeypatch, capsys):
    secret = "private-invalid-token"
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", secret)
    monkeypatch.setattr("sys.argv", ["contextbridge-mcp", "--project-id", "project-a"])
    assert cli.main() == 2
    output = capsys.readouterr()
    assert not output.out
    assert secret not in output.err
    monkeypatch.setattr("sys.argv", ["contextbridge-mcp", "--env-file", "relative.env"])
    assert cli.main() == 2


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_mcp_discovery_validation_and_compact_cards(mode):
    row = memory()
    row["version"]["content"] = "database " * 500
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=[row])

    gateway = MemoryGateway(settings(), httpx.MockTransport(handle))

    async def scenario():
        async with Client(create_server(gateway), mode=mode) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert len(tools) == 6
            assert tools["memory_search"].annotations.read_only_hint
            assert tools["memory_forget"].annotations.destructive_hint
            assert not tools["memory_update"].annotations.idempotent_hint
            assert "project_id" not in tools["memory_write"].input_schema["properties"]
            assert tools["memory_write"].input_schema["additionalProperties"] is False
            result = await client.call_tool("memory_search", {"query": "database"})
            assert not result.is_error
            card = result.structured_content["memories"][0]
            assert card["version"]["content_truncated"]
            assert len(card["version"]["content"]) == 1500
            assert "evidence" not in card["version"]["source"]
            assert result.structured_content["retrieval"] == "lexical"
            invalid = [
                {"query": "database", "project_id": "project-b"},
                {"query": "database", "limit": 6},
                {"query": "database", "limit": True},
                {"query": "database", "as_of": "2026-01-01T12:00:00"},
                {"query": "database", "include_developer": "false"},
            ]
            for args in invalid:
                assert (await client.call_tool("memory_search", args)).is_error
            secret = "sk-" + "x" * 40
            result = await client.call_tool("memory_write", write(source={"evidence": secret}))
            assert result.is_error
            assert secret not in result.model_dump_json()
            result = await client.call_tool("not-a-tool", {})
            assert result.is_error
        assert len(requests) == 1
        request = requests[0]
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        assert json.loads(request.content)["project_id"] == "project-a"

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [401, 403, 404, 409, 422, 500, 307])
def test_http_failures_are_safe_tool_results(status):
    secret = "never-echo-this-backend-input"
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status, json={"detail": secret}, headers={"Location": "https://example.com"}
        )

    async def scenario():
        async with Client(
            create_server(MemoryGateway(settings(), httpx.MockTransport(handle)))
        ) as client:
            result = await client.call_tool("memory_status", {})
            assert result.is_error
            assert secret not in result.model_dump_json()
            assert TOKEN not in result.model_dump_json()
        assert len(calls) == 1  # Redirects must not forward the token to another origin.

    asyncio.run(scenario())


def test_transport_failures_invalid_responses_and_unexpected_errors(caplog):
    async def scenario():
        def fail(request):
            raise httpx.ReadTimeout(TOKEN)

        transports = [
            httpx.MockTransport(fail),
            httpx.MockTransport(lambda _: httpx.Response(200, content="not-json")),
            httpx.MockTransport(lambda _: httpx.Response(200, json={"status": "wrong"})),
            httpx.MockTransport(lambda _: httpx.Response(200, json=[{"invalid": TOKEN}])),
        ]
        for transport in transports:
            async with Client(create_server(MemoryGateway(settings(), transport))) as client:
                result = await client.call_tool("memory_search", {"query": "database"})
                assert result.is_error
                assert TOKEN not in result.model_dump_json()
        gateway = MemoryGateway(settings())

        async def unexpected(args):
            raise RuntimeError(TOKEN)

        gateway.status = unexpected
        async with Client(create_server(gateway)) as client:
            result = await client.call_tool("memory_status", {})
            assert result.is_error
            assert TOKEN not in result.model_dump_json()

    asyncio.run(scenario())
    assert TOKEN not in caplog.text


def test_lost_create_response_never_retries_automatically():
    requests = []

    def timeout(request):
        requests.append(request)
        raise httpx.ReadTimeout(TOKEN)

    async def scenario():
        gateway = MemoryGateway(settings(), httpx.MockTransport(timeout))
        async with Client(create_server(gateway)) as client:
            assert len((await client.list_tools()).tools) == 6
            result = await client.call_tool("memory_write", write())
            assert result.is_error
            assert "may have completed" in result.content[0].text
            assert "request_id" in result.content[0].text
            assert TOKEN not in result.model_dump_json()
        assert len(requests) == 1
        assert requests[0].method == "POST"

    asyncio.run(scenario())


@pytest.mark.parametrize("scope", ["project", "developer"])
def test_search_rejects_unexpected_scope(scope):
    row = memory(scope=scope, project_id="project-b" if scope == "project" else None)

    async def scenario():
        gateway = MemoryGateway(
            settings(), httpx.MockTransport(lambda _: httpx.Response(200, json=[row]))
        )
        async with Client(create_server(gateway)) as client:
            result = await client.call_tool("memory_search", {"query": "database"})
            assert result.is_error
            assert row["id"] not in result.model_dump_json()

    asyncio.run(scenario())


@pytest.mark.integration
def test_two_mcp_clients_share_memory_and_enforce_project_scope(client):
    transport = httpx.ASGITransport(app=client.app)

    def server(agent, project="project-a"):
        config = MCPSettings(
            _env_file=None,
            api_token=client.headers["Authorization"].removeprefix("Bearer "),
            project_id=project,
            agent_id=agent,
            session_id=f"session-{agent}",
        )
        return create_server(MemoryGateway(config, transport))

    async def scenario():
        async with (
            Client(server("codex")) as codex,
            Client(server("claude-code"), mode="legacy") as claude,
            Client(server("other", "project-b")) as other,
        ):
            assert not (await codex.call_tool("memory_status", {})).is_error
            payload = write(conditions={"environment": "dev"})
            result = await codex.call_tool("memory_write", payload)
            assert not result.is_error
            stored = result.structured_content
            memory_id = stored["id"]
            assert stored["version"]["source"]["agent"] == "codex"
            assert stored["version"]["source"]["session"] == "session-codex"
            repeat = await codex.call_tool("memory_write", payload)
            assert repeat.structured_content["id"] == memory_id
            mismatch = await codex.call_tool("memory_write", {**payload, "content": "changed"})
            assert mismatch.is_error
            query = {"query": "PostgreSQL", "conditions": {"environment": "dev"}}
            found = await claude.call_tool("memory_search", query)
            assert found.structured_content["memories"][0]["id"] == memory_id
            unconditioned = await claude.call_tool("memory_search", {"query": "PostgreSQL"})
            assert unconditioned.structured_content["memories"] == []
            assert (await other.call_tool("memory_search", query)).structured_content[
                "memories"
            ] == []
            correction = {
                "memory_id": memory_id,
                "expected_version": 1,
                "content": "Use SQLite for the offline demo",
                "source": {
                    "kind": "user",
                    "interaction": "turn-2",
                    "evidence": "The user changed the offline demo database to SQLite",
                },
            }
            for name, args in [
                ("memory_inspect", {"memory_id": memory_id}),
                ("memory_update", correction),
                ("memory_forget", {"memory_id": memory_id}),
            ]:
                denied = await other.call_tool(name, args)
                assert denied.is_error
                assert "PostgreSQL" not in denied.model_dump_json()
            changed = await claude.call_tool("memory_update", correction)
            assert not changed.is_error
            assert changed.structured_content["current_version"] == 2
            stale = await codex.call_tool("memory_update", correction)
            assert stale.is_error
            inspection = await codex.call_tool("memory_inspect", {"memory_id": memory_id})
            history = inspection.structured_content["history"]
            assert {entry["source"]["agent"] for entry in history} == {"codex", "claude-code"}
            assert len(history) == 2
            assert len(inspection.structured_content["edges"]) == 1
            historical = await codex.call_tool(
                "memory_search", {**query, "as_of": stored["version"]["valid_from"]}
            )
            assert historical.structured_content["memories"][0]["version"]["number"] == 1
            global_memory = await claude.call_tool(
                "memory_write", write(scope="developer", content="Prefer PostgreSQL for services")
            )
            assert not global_memory.is_error
            global_id = global_memory.structured_content["id"]
            global_search = await other.call_tool(
                "memory_search", {"query": "PostgreSQL", "include_developer": True}
            )
            assert [row["id"] for row in global_search.structured_content["memories"]] == [
                global_id
            ]
            direct_global = await codex.call_tool(
                "memory_search", {"query": "PostgreSQL", "scope": "developer"}
            )
            assert direct_global.structured_content["memories"][0]["id"] == global_id
            secret = "sk-" + "z" * 40
            denied = await codex.call_tool("memory_write", write(content=secret))
            assert denied.is_error
            assert secret not in denied.model_dump_json()
            future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
            assert (await codex.call_tool("memory_write", write(valid_from=future))).is_error
            for owner, identity in [(codex, memory_id), (other, global_id)]:
                assert not (
                    await owner.call_tool("memory_forget", {"memory_id": identity})
                ).is_error
                assert (await owner.call_tool("memory_inspect", {"memory_id": identity})).is_error

    asyncio.run(scenario())


def test_readiness_check_outputs_only_safe_configuration(monkeypatch, capsys):
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TOKEN)
    monkeypatch.setattr("sys.argv", ["contextbridge-mcp", "--project-id", "project-a", "--check"])

    async def ready(self, args: NoArguments):
        return {"status": "ready", "project_id": self.settings.project_id}

    monkeypatch.setattr(MemoryGateway, "status", ready)
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "ready", "project_id": "project-a"}

    async def unavailable(self, args):
        raise GatewayError("Memory service unavailable.")

    monkeypatch.setattr(MemoryGateway, "status", unavailable)
    assert cli.main() == 1
    output = capsys.readouterr()
    assert not output.out
    assert "unavailable" in output.err
