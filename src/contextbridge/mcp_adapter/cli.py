import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp.server.stdio import stdio_server
from pydantic import ValidationError

from contextbridge.mcp_adapter.arguments import NoArguments
from contextbridge.mcp_adapter.config import MCPSettings
from contextbridge.mcp_adapter.gateway import GatewayError, MemoryGateway
from contextbridge.mcp_adapter.server import create_server


async def run(settings: MCPSettings, check: bool):
    gateway = MemoryGateway(settings)
    if check:
        print(json.dumps(await gateway.status(NoArguments())))
        return
    server = create_server(gateway)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> int:
    parser = argparse.ArgumentParser(description="ContextBridge local stdio MCP adapter")
    parser.add_argument("--project-id")
    parser.add_argument("--agent-id")
    parser.add_argument("--session-id", help="Use a stable ID when resuming create retries")
    parser.add_argument("--api-url")
    parser.add_argument(
        "--env-file", type=Path, help="Explicit absolute path to a private dotenv file"
    )
    parser.add_argument("--check", action="store_true", help="Check service readiness and exit")
    args = parser.parse_args()
    if args.env_file and (not args.env_file.is_absolute() or not args.env_file.is_file()):
        print("--env-file must name an existing absolute file path.", file=sys.stderr)
        return 2
    values = {
        name: getattr(args, name)
        for name in ("project_id", "agent_id", "session_id", "api_url")
        if getattr(args, name) is not None
    }
    try:
        settings = MCPSettings(_env_file=args.env_file, **values)
    except (ValidationError, OSError):
        print(
            "Invalid adapter configuration. Check project_id, API token, loopback API URL, "
            "and the explicitly selected dotenv file.",
            file=sys.stderr,
        )
        return 2
    try:
        asyncio.run(run(settings, args.check))
    except GatewayError as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
