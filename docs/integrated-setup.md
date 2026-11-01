# Integrated runtime and explicit import (P5)

The configurable runtime connects the merged formation and retrieval modules to the shared
PostgreSQL engine. It supplies the authorized, retention-aware EventReader to admission and uses
one embedding model/dimension pair for both indexing and queries. Providers are explicitly selected
by configuration. Assembly does not download weights, call a provider, or add a second store.
Actual model quality and host compatibility require the separate evidence below.

The built-in [Cloudflare embedding runtime](cloudflare-embeddings.md) can now assemble indexing and
API/MCP retrieval without a custom factory. A custom integration factory retains its own supplied
backends; Cloudflare fills only a missing embedding backend when explicitly configured.

## Clean-machine setup

Install Git, uv, and Docker Compose. Windows uses native PowerShell plus Docker Desktop with Linux
containers; see [Windows setup](windows-setup.md). From a clean checkout of the team's `develop`:

```text
uv sync --frozen --all-extras --python 3.12
uv run python scripts/setup_local.py --project-id contextbridge
docker compose up --build -d
docker compose ps -a
```

Setup creates private `.env` and `.env.mcp` files without replacing existing credentials. Keep their
tokens in sync. The default stack supports explicit writes, keyword search, inspection, correction,
and forgetting without a model. Run the MCP readiness check and registration steps in
[agent integration](agent-integration.md). The viewer can be started with:

```text
uv run --extra viewer streamlit run src/contextbridge/inspection/app.py --server.address 127.0.0.1
```

The viewer uses the existing keyword/browse endpoints and shows stored evidence/history. Rich
retrieval cards in that screen require Harshal's separate viewer work; the new API and MCP tool
already expose them. Do not describe the current viewer's keyword search as semantic retrieval.

## Reviewed provider factory

Set `CONTEXTBRIDGE_CAPTURE_PROJECT_ID=contextbridge` in `.env` before enabling import/workers.
After the team approves providers and their data handling, configure:

```text
CONTEXTBRIDGE_INTEGRATION_FACTORY=your_package.providers:make
CONTEXTBRIDGE_EMBEDDING_MODEL_ID=team-approved-model-and-revision
CONTEXTBRIDGE_EMBEDDING_DIMENSIONS=384
CONTEXTBRIDGE_PROVIDER_TIMEOUT_SECONDS=10
```

These are placeholders, not an installed provider. `make(settings, sessions)` must return
`contextbridge.runtime.IntegrationBackends` with reviewed instances:

| Optional field | Required callable | Meaning |
| --- | --- | --- |
| `extraction_provider` | `generate(event) -> JSON string` | Om's candidate-output provider |
| `formation_verifier` | `verify(candidate, event)` | Om's `supported`/`unsupported`/`uncertain` evidence interface |
| `embedding_backend` | `embed_batch(texts) -> vectors` | Raw embedding backend; optional query-specific method supported |
| `evidence_judge` | `judge(claim, evidence)` | Harshal's `supports`/`contradicts`/`insufficient` judgment interface |
| `consolidator` | `propose(records)` | Om's unchanged V1 proposal interface; actual module still pending |
| `resolution` | `resolve(candidate, context)` | Optional reviewed V1 relation policy; conservative engine default otherwise |

Extraction and its verifier must be supplied together. An embedding backend requires the configured
model/dimensions; those values without a backend or configured Cloudflare provider fail assembly.
A retrieval-only factory
may omit both, returning visibly degraded lexical/identifier results. Missing evidence judgment
remains uncertain when verification is triggered. Graph expansion stays off and high-impact type
selection stays at Harshal's defaults; no shared contract or unapproved product choice is introduced.

The factory owns its supplied providers' model/base URL and private credential configuration; the
built-in Cloudflare fallback uses the documented embedding settings. Use explicit
environment variables/private local configuration, bounded transport deadlines, tool-free calls,
and safe ModuleErrors. `provider_timeout_seconds` bounds the guarded embedding call and is available
to the factory for its other client timeouts; it cannot interrupt arbitrary verifier/extractor code.
Worker process deadlines remain enforced independently. A timed-out embedding thread can finish
later, but commit fences still reject stale mutations. Do not print provider responses or errors.

Package the factory and approved dependencies into the installed environment and container image
(project modules belong under `src`; provider dependencies must be locked by Pranit). An arbitrary
file beside `.env` is not automatically imported into a container. There is no production fixture
factory or model dependency in the default image. API and workers use the same integration setting;
the scheduler requires only model metadata and never invokes model calls itself. Legacy
`CONTEXTBRIDGE_WORKER_FACTORY` still works for existing workers; configuring both factories is
rejected. Remove it when using the integrated factory.

```text
docker compose --profile workers up --build -d
docker compose --profile workers ps -a
```

The scheduler discovers at most 100 current, unindexed versions per pass within its configured
owner/project and opted-in developer scope. Stable per-model/version requests create durable reindex
jobs/outbox IDs. A restart recovers discovery after any API/capture/consolidation write; duplicate
discovery cannot create a second request. No provider call occurs during discovery. Version/scope/
deletion checks repeat at enqueue and commit. Indexing is asynchronous: successful capture means
memory was stored, while pending/failed indexing is disclosed through retrieval degradation.
Previously indexed history remains queryable. Superseded versions missed before discovery need
explicit historical reindex through the existing IndexService library.

Change the model ID when changing weights/revision/vector meaning. A new ID queues the current
versions again; never relabel old vectors or change dimensions under an existing ID. Failed indexing
is not automatically rediscovered forever: inspect safe job status, repair the provider, then enqueue
a new bounded IndexService request with a new request UUID and the authorized version selection.
Existing worker retry/backoff, retention and forgetting rules are in [workers](workers.md).

## Explicit transcript import

Prepare one JSON object matching [CapturedEvent V1](team-plan/fixtures/captured-event.json), with
stable event/message IDs, explicit agent/session/interaction provenance, project, aware occurrence
time, and `{message_id, role, content}` messages. `capture_method` must be `manual_import`.
Source labels are supplied provenance, not host authentication or proof of truth.

The importer invokes Om's transcript normalizer, screens recognized secrets and checks the bound
project **before** HTTP. It reads at most 512 KiB, accepts at most 20 messages/32,000 characters
with 8,000 per message, and rejects duplicate fields/IDs, malformed/future times and oversize input.
It never guesses roles, generates replacement IDs, splits or truncates source evidence. Divide a
long transcript deliberately into complete bounded interactions, each with its own stable event ID;
review each interaction for adequate evidence. Developer import requires both `--allow-developer`
and the service's explicit developer-capture opt-in.

Use the actual absolute `.env.mcp` path on your machine in Bash or PowerShell:

```text
uv run contextbridge-import --project-id contextbridge --env-file /ABS/ContextBridge/.env.mcp validate event.json
uv run contextbridge-import --project-id contextbridge --env-file /ABS/ContextBridge/.env.mcp submit event.json
uv run contextbridge-import --project-id contextbridge --env-file /ABS/ContextBridge/.env.mcp status JOB_UUID
```

`validate` is offline and prints IDs/count only. `submit` makes one request and prints the durable
acknowledgement; it does not wait for extraction. `status` prints the content-free capture status.
No implicit dotenv file, remote origin, proxy environment or redirect is used. A cross-machine
client uses the documented SSH loopback tunnel in [live tests](live-agent-test.md).

A lost response may have accepted the event. Keep its original IDs and identical payload for an
explicit retry; the importer never retries automatically. Changed payloads conflict; expired or
forgotten events stay cancelled. Never mint a new ID to bypass cancellation. The service erases
its buffers according to [retention](ingestion.md); the original local import file and external agent
logs are separate user-owned copies. No automatic host capture hook has been verified or enabled.

## Recovery and verification

| Symptom | Action |
| --- | --- |
| Port already used | Choose a free DB port in `.env` and update the matching host database URL; retain named volumes |
| Readiness fails | Inspect `docker compose ps -a` and migration completion; correct configuration and restart |
| Import reports `OUT_OF_SCOPE` | Check project binding, token and developer opt-in; do not relabel an unrelated event |
| Job stays queued | Check worker/scheduler/Redis services and their provider factory; accepted data remains durable |
| Provider is unavailable/malformed | Repair the approved backend; use safe job status and bounded retries; retain original event IDs |
| Rich search is disabled | Configure the integrated factory; legacy keyword tools remain available |
| Rich search is degraded | Check extension availability, model/dimensions, pending/failed indexes and provider health; show warnings |
| Correction conflicts | Inspect current evidence/version, then submit a reviewed correction with its expected version |
| Forget cancelled buffered imports | P4 intentionally clears all pending buffers in that same owner/scope/project; do not replay them |

Do not use `docker compose down --volumes` to recover ordinary startup failures. It destroys data.
Backups/WAL and external client copies have separate retention. Use the dedicated `_test` database
instructions for testing; never point pytest or migration downgrade at the normal Compose DB.

The automated integration test exercises explicit import → actual Extractor/AdmissionPolicy →
stored version → guarded recorded embeddings/pgvector retrieval → actual viewer evidence client →
MCP correction → fresh MCP-session read → forgetting/replay fence. Native stdio subprocess tests
cover the additional retrieval tool. The disposable Compose probe repeats the assembled module
flow, automatic indexing, whole-stack restarts and forgetting. Its test-only image includes recorded
synthetic backends; production images do not. These checks validate wiring and storage behavior,
not model meaning, real host approval flows or accuracy.

## Supported-feature and release evidence

| Capability | Evidence/status |
| --- | --- |
| Explicit API and six original MCP operations | Existing PostgreSQL/native Linux/Windows CI and stdio checks |
| Seventh `memory_retrieve` tool | Additional V1 card retrieval; degradation/warnings preserved, project bound, max five cards |
| Manual import and actual module assembly | Automated PostgreSQL/API/module tests with recorded synthetic backends |
| Durable workers/reindex/forget/restarts | Real Redis/Celery and disposable Linux Compose checks |
| Viewer evidence/history/correction/confirmed delete | Harshal's merged screen/client tests; current viewer search remains keyword |
| Real extraction, embeddings, verifier and consolidation quality | Pending team provider choices, Om O3/O4 and approved labelled reports |
| Live Codex-to-Codex across networks | Previously reported by Pranit/Om for explicit memory operations |
| Actual Claude Code, same-device cross-agent and new host tests | Pending manual host evidence; MCP client labels alone do not prove compatibility |
| Native Windows | GitHub CI; numerical vector/prefork checks explicitly run in Linux jobs |
| Windows Docker Desktop complete flow | Pending teammate host verification |
| V1 release | Pending all [release gates](team-plan/README.md#required-release-gates), quality reports and team review; team handles `main` |

Record provider/model/prompt revision, approved privacy/budget, fixed holdout fingerprints, independent
labels, keyword baseline, latency and cost (or explicit unavailable values) with the module owners.
Do not invent target accuracy, use coverage as quality evidence or tune on holdout cases. Complete
the live Codex/Claude walkthrough on both machines and record the full Windows Docker flow before
claiming finished V1 support. This P5 wiring does not satisfy those external gates by itself.
