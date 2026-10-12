# Cloudflare embeddings: server indexing and agent retrieval

The configured hosted model is `@cf/qwen/qwen3-embedding-0.6b`. Model execution happens at
Cloudflare; no model weights, additional SDK, or schema migration are needed. Harshal's embedding
backend ownership transfer to Pranit was explicitly authorized for this change. Formation
algorithms and viewer search are outside this scope.

## Configuration and startup

Keep these settings in the private `.env` file; do not commit or paste their values into logs:

```text
CONTEXTBRIDGE_EMBEDDING_PROVIDER=cloudflare
CONTEXTBRIDGE_EMBEDDING_API_KEY=YOUR_WORKERS_AI_TOKEN
CONTEXTBRIDGE_EMBEDDING_BASE_URL=https://api.cloudflare.com/client/v4/accounts/YOUR_ACCOUNT_ID/ai/v1
CONTEXTBRIDGE_EMBEDDING_MODEL_ID=@cf/qwen/qwen3-embedding-0.6b
CONTEXTBRIDGE_CAPTURE_PROJECT_ID=YOUR_PROJECT
```

Use an actual 32-character hexadecimal account ID in the URL. No separate account setting is
required. The API token needs Workers AI access for that account. This specific model defaults to
1024 dimensions; explicitly setting a different width is rejected. Only the official HTTPS account
endpoint is allowed, without URL credentials, query parameters, redirects, or proxy environment.

From the repository, run:

```text
uv sync --frozen --all-extras
docker compose --profile workers up --build -d
docker compose --profile workers ps -a
```

Compose passes the embedding settings to the API, worker, and scheduler. The scheduler does not
call Cloudflare. Existing database volumes and `.env` files are retained. The default project
binding is intentionally empty: set `CONTEXTBRIDGE_CAPTURE_PROJECT_ID` to the project whose
stored memories may be sent to Cloudflare. Developer-wide indexing additionally requires
`CONTEXTBRIDGE_CAPTURE_ALLOW_DEVELOPER=true`. Enabling this runtime sends those stored memory
texts and search queries to Cloudflare; source evidence is not included in requests.

Without an integration factory, the built-in runtime assembles the actual guarded embedding backend
and retriever. Workers dispatch/claim/backfill only reindex work; capture and consolidation stay
queued until a reviewed integration factory supplies their providers. Expiry/retention still apply.
The embedding runtime rejects the legacy worker-only factory because it cannot provide a shared
API/worker backend. Use `CONTEXTBRIDGE_INTEGRATION_FACTORY` when combining providers.

With an integration factory, its supplied backends remain authoritative. Cloudflare fills only a
missing `embedding_backend`; it does not replace extraction, verification, consolidation, resolution,
or an existing embedding backend. The factory's embedding output must still match the configured
model and dimensions. No provider call happens during assembly.

## Save, search, correct, forget

1. Explicit API/MCP writes save evidence-backed memories in PostgreSQL. Existing stored current
   versions in the configured scope are also discovered for indexing.
2. The scheduler discovers at most 100 missing current versions per pass and creates durable
   version/model-linked reindex jobs. Redis carries IDs only. The worker embeds memory content
   as documents and stores validated vectors through the existing transactional IndexService.
3. `POST /v1/retrieval/search` and MCP `memory_retrieve` use the richer retriever. Each search
   embeds its query and combines semantic, lexical, and symbolic channels. The original
   `memory_search` and viewer search remain keyword based.
4. Corrections preserve old versions and queue the new current version on the next sweep.
   Already indexed historical versions remain searchable with an explicit `as_of` time. A version
   superseded before discovery needs explicit authorized historical reindexing through IndexService.
5. Forget removes content, evidence, vectors, and related records. Existing commit fences prevent
   an in-flight embedding response or redelivered job from resurrecting forgotten content.

API and MCP V1 response shapes are unchanged. Scope, conditions, types, and time come from caller
filters; the query instruction does not infer these filters. Semantic failure retains explicit
keyword fallback with `degraded=true` and `EMBEDDING_UNAVAILABLE` (or the existing repository
warning). A write succeeding does not guarantee that background indexing has finished.

Documents are sent unchanged. Queries use the fixed `Instruct: <task>\nQuery: <query>` format,
where task is:

> Given a software development question, retrieve relevant developer and project memories that
> help answer the question.

Changing document preprocessing or model vector meaning requires a new model identity and
reindexing; never relabel existing vectors. Query instruction changes need retrieval reevaluation.

## Bounds and recovery

The guard limits original text to 8000 characters, uses batches of at most 32, and one overall
provider deadline (default 10 seconds). Cloudflare additionally limits each formatted input to
8192 UTF-8 bytes, request JSON to 1 MiB, and uncompressed response JSON to 2 MiB. These conservative
input bounds avoid silently truncating content; they are not an exact tokenizer. Oversize inputs
and recognized secrets fail before HTTPS. Compressed responses are rejected to keep decoding bounded.

Responses must contain one uniquely indexed numeric, finite, 1024-dimensional vector per input.
Indices restore request order. Out-of-range float32 values, incorrect model labels when present,
malformed JSON, duplicate indices, wrong counts, and wrong widths fail safely. Credentials, request
content, provider bodies, and exception chains are not returned or logged by the adapter.

The HTTP client never retries. Timeouts, connection failures, 408/429, and server failures use safe
retryable codes. Authentication, other client errors, redirects, and invalid outputs do not retry.
Background jobs use existing bounded attempts/backoff. Check authenticated
`GET /v1/worker/jobs/{work_id}` for content-free status. After exhausted attempts, repair the
configuration and enqueue a new authorized bounded IndexService request with a new request UUID;
the sweep does not rediscover a failed request indefinitely.

## Verification and limits of the evidence

Ordinary tests use synthetic HTTP responses, with hosted credential settings cleared. The live
probe is an explicit separate command; it refuses non-loopback/non-`_test` or nonempty databases,
uses only its four fixed synthetic memories, and never touches the configured development database:

```text
uv run python scripts/embedding_probe.py --execute --confirm-free-plan --database-url POSTGRESQL_PSYCOPG_LOOPBACK_TEST_URL --max-calls 20 --report LOCAL_REPORT.json
```

Prepare a fresh migrated disposable `_test` database first. `--confirm-free-plan` records the
operator's account-plan confirmation; it does not inspect Cloudflare billing. Calls are sequential,
counted, capped at 20, and stop at the first provider failure. Re-running consumes a new allocation
of calls and requires a fresh database. Avoid repeated probes; Free account quota is shared.

The [2026-10-12 live result](../evaluation/embeddings/cloudflare-qwen3-20261012.json) used 10 requests,
observed 1024 dimensions, and retrieved the intended memory first among three distractors with a
paraphrased query. It passed restart/replay, correction, historical retrieval, and forgetting through
fresh MCP SDK sessions. API/MCP ran in process, while Cloudflare HTTPS and PostgreSQL were real.
This is one synthetic demonstration, not a general accuracy report or an installed-host test.
Billing usage was not measured; no paid upgrade was authorized.

Protocol references: [Cloudflare OpenAI compatibility](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/),
[hosted model/context](https://developers.cloudflare.com/workers-ai/models/qwen3-embedding-0.6b/),
and [Qwen dimensions/query instruction](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).
