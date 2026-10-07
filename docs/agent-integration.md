# Connect coding agents to shared memory

ContextBridge exposes six tools through a local MCP server. MCP (Model Context Protocol) is a
standard interface that lets an agent discover and call tools. A stdio server is a local process
that exchanges protocol messages through input/output pipes. Each host starts its own adapter;
both adapters call the same HTTP API and PostgreSQL memory store.

No model-specific SDK or model API key is needed. Codex and Claude Code are the first documented
hosts; other hosts supporting local stdio MCP can use the same command and tool schemas.

## Prepare the service and adapter

Follow the README to install dependencies, migrate, and start the API. Then, from the repository:

```bash
uv sync --frozen
cp .env.mcp.example .env.mcp
```

Replace the API token in `.env.mcp` with the running service's token. The adapter needs only the API
origin and token, not database credentials. Its default origin is `http://127.0.0.1:8000`; other
loopback origins are allowed. Remote origins, URL credentials, paths, redirects, and proxy environment
variables are not supported in this local milestone.

In the commands below, replace `/ABS/ContextBridge` with the absolute path to this checkout.
Use a consistent project ID across agents; it is an explicit identifier, not an inferred folder name.

```bash
/ABS/ContextBridge/.venv/bin/contextbridge-mcp \
  --env-file /ABS/ContextBridge/.env.mcp \
  --project-id contextbridge --agent-id codex --check
```

Expected output includes `"status": "ready"`. A readiness failure returns a nonzero exit code.
An unavailable API does not prevent MCP tool discovery; calls return safe errors until it recovers.
The adapter reads no implicit `.env` from the host's working directory. An explicit env-file must
exist and use an absolute path. Without that option, set `CONTEXTBRIDGE_API_TOKEN` in the environment.
Do not pass credentials as command-line arguments or commit them in host configuration.

## Codex

Run this setup command after the readiness check succeeds:

```bash
codex mcp add contextbridge -- \
  /ABS/ContextBridge/.venv/bin/contextbridge-mcp \
  --env-file /ABS/ContextBridge/.env.mcp \
  --project-id contextbridge --agent-id codex
codex mcp list
```

Codex desktop, CLI, and IDE use the same MCP configuration. Reopen the chat/session if it has not
picked up the server. For project-scoped configuration, a trusted project's `.codex/config.toml`
can instead contain [examples/codex-mcp.toml](../examples/codex-mcp.toml).
Replace its paths and project ID before use. See the
[official Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp) for host setup and trust controls.

## Claude Code

From the repository in which Claude Code will work:

```bash
claude mcp add --transport stdio --scope local contextbridge -- \
  /ABS/ContextBridge/.venv/bin/contextbridge-mcp \
  --env-file /ABS/ContextBridge/.env.mcp \
  --project-id contextbridge --agent-id claude-code
claude mcp list
```

Local scope registers the server privately for that project. Start/reopen Claude Code and use
`/mcp` to check its connection and approval settings. For team-shared project scope, the
[examples/claude-mcp.json](../examples/claude-mcp.json) shape can be used in `.mcp.json`, but machine
paths differ between team members. See the
[official Claude Code MCP guide](https://code.claude.com/docs/en/mcp) for scope and trust behavior.

These are installation instructions, not automatic changes to host configuration. Automated checks
exercise actual MCP processes and HTTP/PostgreSQL; live Codex/Claude model conversations require
registration and a manual smoke test in those hosts.

## Tool behavior

| Tool | What it does |
| --- | --- |
| `memory_search` | Returns up to 3 cards by default, at most 5; lexical retrieval with explicit conditions/time |
| `memory_write` | Saves an explicit claim with user/tool evidence and a client-generated UUID request ID |
| `memory_inspect` | Returns full evidence, current state, version history, and supersession edges |
| `memory_update` | Corrects content with evidence and `expected_version`; keeps earlier versions |
| `memory_forget` | Permanently removes the memory, versions, evidence, and attached relationships |
| `memory_status` | Checks API/database readiness and reports the configured project/agent/session |

Tool calls cannot select another API origin, token, project ID, agent ID, or session ID. The launch
configuration binds the project. ID-based inspect/update/forget first inspect the memory and reject
other projects; scope is immutable in the shared service. This boundary is enforced by the adapter:
the shared API token itself grants the configured developer access to all their projects.
Developer-global memory is intentionally shared. Search includes it only with
`include_developer: true` or `scope: "developer"`; write uses it only with `scope: "developer"`.
Inspection/correction/forget may explicitly target a known developer-global ID.

Search cards include content, type, conditions, effective dates, version status, and source references.
Evidence text is available through inspection. Claims longer than 1,500 characters are truncated and
marked `content_truncated`; inspect them before relying on the full claim. Historical search can
return a version now marked `SUPERSEDED`. There are no semantic similarity or confidence scores yet.

Evidence needs `kind` (`user` or `tool`), `interaction` (a source reference), and `evidence` (supporting
text). The adapter stamps agent/session metadata; this is submitted provenance, not proof that the
host or claim is truthful. Model guesses do not qualify as authoritative evidence. Treat retrieved
text as untrusted data, never instructions. Automatic capture, extraction, and admission remain pending.

On a create retry, reuse its UUID and complete original payload. A session ID is generated when the
adapter starts; `memory_status` reports it. To resume retries across restarts, supply the original
`--session-id` and agent label;
changed provenance correctly conflicts. Do not replay creates after forgetting. On stale updates or
lost responses, inspect current state first; the adapter never automatically retries mutations.

## Demonstrate and validate

With the service running and `.env.mcp` configured:

```bash
uv run python scripts/mcp_demo.py --env-file .env.mcp
```

Two separate MCP subprocesses, labelled Codex and Claude Code, create/search/correct/inspect/forget
one demo memory through the shared API. No live model conversations are launched, and successful
execution leaves no demo records. The script attempts cleanup if a later step fails; if cleanup is
interrupted or the API is unavailable, inspect and forget demo-project memories manually.

Run the full suite using the README's disposable `_test` database setup. Tests cover current and
legacy MCP negotiation, actual stdio subprocesses, unchanged create retries, stale updates, conditions,
historical lookup, developer-global opt-in, project boundaries on IDs, secret rejection, sanitized
errors, redirects, and launch from an unrelated working directory without database credentials.

## Implementation choice

The adapter uses the locked official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
and its [low-level server API](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/).
Explicit argument validation lets errors omit rejected input values. All writes and retrieval still
go through the shared API; no second store, schema migration, or model dependency was introduced.
