# Use ContextBridge V1

One configured developer owns the store. Models run online through Groq and Cloudflare; you do
not install an AI model. Keep the existing `.env`, `.env.mcp` and database volume.

## Start

Use the same project ID in the runtime, viewer and agents. Replace `contextbridge` below if yours
differs. Your private `.env` needs the existing database/API settings, the four Cloudflare embedding
settings and the Groq formation settings in [V1 integration](v1-integration.md).

```text
uv sync --frozen --all-extras --python 3.12
uv run python scripts/start_v1.py --project-id contextbridge --free-groq-confirmed --action check
uv run python scripts/start_v1.py --project-id contextbridge --free-groq-confirmed --action start
uv run python scripts/start_v1.py --project-id contextbridge --free-groq-confirmed --action viewer
```

The confirmation flag means the Groq account is Free with paid usage disabled. The first check
validates configuration without contacting models or the database. Start launches the existing
Compose API/database and optional workers; viewer opens Streamlit on `http://127.0.0.1:8501`.
The helper enables V1 settings only for its child processes and never edits credential files.
Stopping the viewer does not erase memories. `docker compose down` preserves the data volume.

Starting workers can process already-buffered events in the chosen binding. Developer-wide
processing/indexing is enabled only by the explicit `CONTEXTBRIDGE_CAPTURE_ALLOW_DEVELOPER=true`
setting; leave it false for project-only processing. The viewer can save/browse/manage shared
memories independently and displays whether indexing is configured for their binding.

## Walk through the features

1. **Save:** enter a confirmed short fact, its type and supporting statement. Choose project or
   shared scope. Open details to see evidence and indexing progress.
2. **Import:** paste a chosen JSON message list with explicit roles and a timezone-aware timestamp.
   Submit once, then check progress. Nothing automatically captures an agent's conversation.
3. **Search:** ask a question. Three cards are returned; more context allows five. Supply condition
   and historical-time filters explicitly. Read any reduced-service or uncertain-evidence warning.
4. **Inspect/correct:** read evidence and history, then supply corrected text and fresh evidence.
   A stale version is rejected; review the current version before submitting again.
5. **Consolidate:** queue compatible current memories in Maintenance. Workers preserve originals
   and add a summary only after source/proposal checks. Details expose original summary evidence.
6. **Retire/restore:** retire stops current use while keeping history and affected summaries inactive.
   Find it in retired listing and restore an earlier version with fresh evidence. This creates a
   new version. Rebuild generated summaries instead of restoring them.
7. **Forget:** explicitly confirm permanent removal. Stored content, history, evidence, vectors and
   related derived content/jobs are removed. Old imports cannot recreate the forgotten content.

Automatic consolidation is opt-in through the helper: one batch every 15 minutes, at most 20
compatible current clear memories. Generated/retired/disputed memories are excluded. An unchanged
batch is attempted once; source changes or a reviewed policy revision are required for a new batch.
The existing seven MCP tools remain compatible; `memory_retire` and `memory_restore` add lifecycle
controls. See [agent integration](agent-integration.md) for registration and project binding.

## Repeatable checks

Ordinary tests must use a migrated dedicated database ending `_test`, as described in the README.
Use synthetic providers; they never require real credentials. The cross-platform full-stack check
owns its temporary test project and volumes, then removes only those resources:

```text
uv run --all-extras python scripts/worker_stack_probe.py
```

On Windows, run that command in PowerShell with Docker Desktop using Linux containers. A PASS must
include restart, retirement/restoration, forgetting and replay checks. Record the commit and output.
Native Windows CI passing does not establish Docker Desktop passing.

For an explicitly authorized online check, create a **new empty migrated** loopback PostgreSQL
database named `contextbridge_v1_live_test`. Set `CONTEXTBRIDGE_V1_DEMO_DATABASE_URL` privately to
that database. Use an unused private output directory, then run:

```text
uv run --all-extras python -m scripts.v1.demo --directory /absolute/path/to/private/demo-output --free-groq-confirmed --hosts
```

This sends only fixed short synthetic statements, never existing private memories. It starts a
temporary local API, uses the actual hosted adapters through durable workers, and optionally invokes
installed Codex/Claude sessions with only the synthetic MCP server. It leaves installed host
registration unchanged and removes synthetic content on completion. Its numeric SQLite ledger
serializes calls across processes, counts attempts before HTTP and never resets an existing ledger.
Ceilings are **40 Groq / 20 Cloudflare**, sequential, without retries. The first provider/quota
failure stops both routes; unavailable later steps are recorded as unattempted. This verification
ledger is not a memory store or production component.

The current approval's online run has already stopped after HTTP 400. Do not start another live run
under that approval. A future run needs a new bounded verification request. Claude requires its own
normal login; it remains pending by the user's choice. The [check report](v1-completion.md) records
what worked, failed and was not attempted.
