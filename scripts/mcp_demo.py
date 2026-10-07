"""Exercise two real MCP subprocesses against a running API; no LLM/API key needed."""

import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from mcp import Client, StdioServerParameters


async def demo(env_file: Path):
    def agent(name):
        return Client(
            StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "contextbridge.mcp_adapter.cli",
                    "--env-file",
                    str(env_file),
                    "--project-id",
                    "contextbridge-mcp-demo",
                    "--agent-id",
                    name,
                ],
            ),
            read_timeout_seconds=15,
        )

    async def call(client, name, args):
        result = await client.call_tool(name, args)
        if result.is_error:
            raise RuntimeError(
                "Demo tool failed; check service readiness and private configuration"
            )
        return result.structured_content

    async with agent("codex") as codex, agent("claude-code") as claude:
        await call(codex, "memory_status", {})
        print("Both MCP clients connected to the shared service.")
        created = await call(
            codex,
            "memory_write",
            {
                "request_id": str(uuid4()),
                "type": "DECISION",
                "content": "Use PostgreSQL for the ContextBridge demo",
                "source": {
                    "kind": "user",
                    "interaction": "demo-turn-1",
                    "evidence": "Demo scenario: user explicitly chose PostgreSQL",
                },
            },
        )
        identity = {"memory_id": created["id"]}
        try:
            found = await call(claude, "memory_search", {"query": "PostgreSQL"})
            if not any(row["id"] == created["id"] for row in found["memories"]):
                raise RuntimeError("Independent client did not retrieve the demo memory")
            print("Second MCP client retrieved the first client's PostgreSQL decision.")
            await call(
                claude,
                "memory_update",
                {
                    **identity,
                    "expected_version": 1,
                    "content": "Use SQLite for the offline ContextBridge demo",
                    "source": {
                        "kind": "user",
                        "interaction": "demo-turn-2",
                        "evidence": "Demo scenario: user explicitly switched to SQLite offline",
                    },
                },
            )
            inspected = await call(codex, "memory_inspect", identity)
            if len(inspected["history"]) != 2 or len(inspected["edges"]) != 1:
                raise RuntimeError("Demo history or supersession edge was not preserved")
            print("First client inspected the new SQLite decision and both evidence versions.")
        finally:
            await call(codex, "memory_forget", identity)
            print("Demo memory, versions, evidence, and relationship removed.")
        missing = await claude.call_tool("memory_inspect", identity)
        if not missing.is_error:
            raise RuntimeError("Forgotten demo memory is still accessible")
        print("MCP demo passed. These are protocol clients, not live model conversations.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    env_file = args.env_file.resolve()
    if not env_file.is_file():
        parser.error("Create a private dotenv configuration before running the demo")
    asyncio.run(demo(env_file))


if __name__ == "__main__":
    main()
