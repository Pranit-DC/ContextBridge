# ContextBridge V1 on Linux

Use one project ID in the service, viewer and Codex. The examples use `contextbridge`; replace it
with your chosen project ID. Your existing private `.env` and `.env.mcp` stay in place. Groq and
Cloudflare run online. PostgreSQL, Redis, the API and workers run in Docker on your laptop.

## Start the application

Install the locked optional packages once:

```bash
cd /home/pranitchiman/Projects/ContextBridge
uv sync --frozen --all-extras --python 3.12
```

Start V1 with one command:

```bash
uv run python scripts/run_v1_linux.py --project-id contextbridge --free-groq-confirmed
```

The command validates settings, builds/starts the existing Docker services, waits for API/schema
readiness, checks the exact capture-project binding and configured providers, starts the viewer,
and opens `http://127.0.0.1:8501` after the viewer is ready. Keep the terminal open. `Ctrl+C` stops
the viewer while background services and saved data remain available. If the viewer is already
running, select the same project in its sidebar. An occupied port belonging to another service
produces an explicit error; use `--viewer-port 8502` instead.

`--free-groq-confirmed` records your confirmation that paid Groq usage is disabled. Configuration
readiness does not contact the models or certify model accuracy. To check configuration without
starting anything, add `--action check`. To stop background services while keeping data, use:

```bash
uv run python scripts/run_v1_linux.py --project-id contextbridge --action stop
```

## Enter your own information

- **Save** accepts a confirmed fact, decision, preference, state, event or lesson. Enter both the
  memory text and its supporting statement. For your own confirmed statement, the supporting text
  can be the same sentence. Empty fields produce a visible message; successful saves show a
  persistent confirmation and evidence/history. The selected tab survives form submissions.
- **Import → My own statement** accepts your own words in ordinary language. Click **Import
  conversation**, then **Check import progress**. AI proposes atomic memories; unsupported or
  unclear statements remain pending. Use **Message list (JSON)** when importing other speakers
  so their actual roles stay intact. Assistant text is not authoritative evidence.
- **Processing activity → Refresh processing activity** shows the latest 20 import/Codex jobs
  for this project's owner. It displays accepted work separately from finished, deferred or failed
  processing and provides buttons to inspect saved results.
- **Browse → Open details** shows evidence, history and meaning-search indexing. Wait for
  indexing to succeed before expecting semantic matches. A saved memory may be usable by words
  while background indexing is still pending.
- **Search** returns relevant saved information, not general internet answers. Questions about
  topics absent from your memories should return no relevant memory. The semantic channel filters
  cosine similarity below `CONTEXTBRIDGE_RETRIEVAL_MIN_SIMILARITY` (default `0.4`) before limiting
  results. This is a configurable relevance bound, not a calibrated accuracy score; similar wording
  can still produce imperfect matches. Words and identifiers remain independent retrieval channels.
- **Details** provides correction with evidence, retirement, restoration and confirmed permanent
  forgetting. Original versions remain visible until forgetting. **Maintenance** submits a bounded
  source-backed consolidation batch and shows its actual status; a valid summary is not guaranteed.

No application answer is selected from a predefined demonstration list. Input limits, evidence,
scope and secret checks still apply to arbitrary text. Pending or rejected inputs are valid outcomes
when saving would require a guess; they must be visible.

## Connect Codex and enable capture

MCP and capture are separate capabilities. MCP lets Codex read/manage memories. The opt-in
`UserPromptSubmit` hook forwards future user messages from one configured workspace to the same
processing pipeline. It does not scan old chats or infer assistant/tool authority. Short stand-alone
facts work best; an ambiguous reply such as “yes” may need explicit context or a manual import.

Prepare the private adapter configuration if necessary:

```bash
uv run python scripts/setup_local.py --project-id contextbridge
```

Existing `.env` and `.env.mcp` are preserved. Register a separate Codex connection:

```bash
codex mcp add contextbridge-v1 -- \
  /home/pranitchiman/Projects/ContextBridge/.venv/bin/python \
  -m contextbridge.mcp_adapter.cli \
  --env-file /home/pranitchiman/Projects/ContextBridge/.env.mcp \
  --project-id contextbridge --agent-id codex
```

Enable capture only in the workspace whose messages you want processed:

```bash
uv run python scripts/connect_codex_capture.py --project-id contextbridge --install
```

This merges the ContextBridge hook into project-local `.codex/hooks.json`, preserving other hooks.
Start a fresh Codex session and review/trust it through the normal `/hooks` flow. Do not bypass that
review. Without `--install`, the command generates an inactive `.contextbridge/codex-hooks.json`
for inspection. Codex hook availability/trust is a host requirement; see
[official hook documentation](https://learn.chatgpt.com/docs/hooks).

After a new message, the hook reports that processing was queued, or clearly reports capture
failure. Open the viewer's Import tab and refresh processing activity. Inspect the resulting
memories and evidence. In a fresh Codex session, ask it to use `contextbridge-v1` and
`memory_retrieve`/`memory_inspect` before answering from saved context.

The hook keeps empty receipt files containing only event identity and file time, so retries reuse
one event without keeping hidden local message copies. Retrying a forgotten or expired event stays
cancelled at the server. Remove the ContextBridge hook entry to turn capture off. Other agent hooks
are not covered by this Linux workflow.

## Provider checks and validation

The connectivity-check command makes **one Groq and at most two Cloudflare** synthetic requests,
stops on failure, and refuses to reuse/reset an already-used ledger or overwrite a report. It sends
no saved memories. Run only under a fresh explicitly bounded verification authorization:

```bash
uv run python -m scripts.check_v1_providers \
  --ledger /absolute/private/path/unused-check.sqlite \
  --report /absolute/private/path/new-report.json --free-groq-confirmed
```

Ordinary tests never use real credentials. Full PostgreSQL tests require a dedicated `_test`
database and isolated Redis as described in the README. The Linux full-stack check creates and
removes its own test services/volumes:

```bash
uv run --all-extras python scripts/worker_stack_probe.py
```

Read [the Linux verification report](linux-v1-verification.md) for observed results and limitations.
