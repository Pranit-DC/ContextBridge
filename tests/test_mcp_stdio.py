import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from mcp import Client, StdioServerParameters
from sqlalchemy import text

from tests.conftest import TEST_TOKEN


@pytest.fixture
def running_api(database, tmp_path):
    database_url, _ = database
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "contextbridge.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "CONTEXTBRIDGE_DATABASE_URL": database_url,
            "CONTEXTBRIDGE_API_TOKEN": TEST_TOKEN,
            "CONTEXTBRIDGE_DEVELOPER_ID": "stdio-test-developer",
            "CONTEXTBRIDGE_CAPTURE_PROJECT_ID": "stdio-project",
            "CONTEXTBRIDGE_INTEGRATION_FACTORY": "tests.integration.provider_factory:make",
            "CONTEXTBRIDGE_EMBEDDING_MODEL_ID": "recorded-integration-v1",
            "CONTEXTBRIDGE_EMBEDDING_DIMENSIONS": "2",
            "CONTEXTBRIDGE_WORKER_FACTORY": "",
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        with httpx.Client(base_url=url, timeout=1, trust_env=False) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail("Disposable API process exited before readiness")
                try:
                    if client.get("/health/live").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("Disposable API did not start within 15 seconds")
        yield url
    finally:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_real_stdio_processes_share_the_api_without_database_credentials(
    running_api, database, tmp_path, mode
):
    # The adapter must ignore an unrelated repository's dotenv file.
    (tmp_path / ".env").write_text("CONTEXTBRIDGE_API_TOKEN=wrong-token\n")

    def agent(name):
        return Client(
            StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "contextbridge.mcp_adapter.cli",
                    "--project-id",
                    "stdio-project",
                    "--agent-id",
                    name,
                ],
                env={
                    "CONTEXTBRIDGE_API_URL": running_api,
                    "CONTEXTBRIDGE_API_TOKEN": TEST_TOKEN,
                },
                cwd=tmp_path,
            ),
            mode=mode,
            read_timeout_seconds=10,
        )

    async def scenario():
        async with agent("codex") as codex, agent("claude-code") as claude:
            assert len((await codex.list_tools()).tools) == 10
            status = await claude.call_tool("memory_status", {})
            assert not status.is_error
            assert status.structured_content["project_id"] == "stdio-project"
            created = await codex.call_tool(
                "memory_write",
                {
                    "request_id": str(uuid4()),
                    "type": "DECISION",
                    "content": "Use PostgreSQL in the stdio prototype",
                    "source": {
                        "kind": "user",
                        "interaction": "stdio-turn-1",
                        "evidence": "The user chose PostgreSQL for this prototype",
                    },
                },
            )
            assert not created.is_error
            memory_id = created.structured_content["id"]
            found = await claude.call_tool("memory_search", {"query": "PostgreSQL"})
            assert found.structured_content["memories"][0]["id"] == memory_id
            rich = await claude.call_tool("memory_retrieve", {"query": "PostgreSQL"})
            assert not rich.is_error
            assert rich.structured_content["cards"][0]["memory_id"] == memory_id
            assert rich.structured_content["degraded"]
            assert "EMBEDDING_UNAVAILABLE" in rich.structured_content["warnings"]
            changed = await claude.call_tool(
                "memory_update",
                {
                    "memory_id": memory_id,
                    "expected_version": 1,
                    "content": "Use SQLite for the offline prototype",
                    "source": {
                        "kind": "user",
                        "interaction": "stdio-turn-2",
                        "evidence": "The user changed the offline prototype database to SQLite",
                    },
                },
            )
            assert not changed.is_error
            inspected = await codex.call_tool("memory_inspect", {"memory_id": memory_id})
            assert len(inspected.structured_content["history"]) == 2
            assert inspected.structured_content["memory"]["version"]["source"]["agent"] == (
                "claude-code"
            )
            context = await codex.call_tool(
                "memory_context",
                {
                    "memory_id": memory_id,
                    "expected_version": 2,
                },
            )
            assert not context.is_error
            entries = context.structured_content["items"]
            assert [entry["role"] for entry in entries] == ["seed", "historical"]
            assert "SQLite" in entries[0]["content"] and "PostgreSQL" in entries[1]["content"]
            assert entries[1]["applicable_at_query"] is False
            assert not (await codex.call_tool("memory_forget", {"memory_id": memory_id})).is_error
            assert (await codex.call_tool("memory_context", {"memory_id": memory_id})).is_error
            assert (await claude.call_tool("memory_inspect", {"memory_id": memory_id})).is_error

    asyncio.run(scenario())
    _, engine = database
    with engine.connect() as connection:
        for table in ("memories", "memory_versions", "memory_edges"):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
