# User-configurable formation provider

Each local ContextBridge installation can choose its extraction model, verification model,
provider, endpoint and API key. This is single-developer local configuration, not a multi-user
credential store or a viewer settings screen. Formation provides injectable adapters and a
proposal-only runner; shared service/worker wiring belongs to Pranit and viewer wiring to Harshal.

## Where to put your key

Add these settings to the project's existing **`.env`**, beside `README.md`. Preserve existing
database/API settings. Replace the model placeholder with an explicitly chosen available model ID;
do not paste your actual key into chat, commands, transcripts, fixtures or committed files.

```dotenv
CONTEXTBRIDGE_FORMATION_PROVIDER=openrouter
CONTEXTBRIDGE_FORMATION_MODEL=YOUR_CHOSEN_MODEL_ID:free
CONTEXTBRIDGE_FORMATION_API_KEY=YOUR_OWN_PROVIDER_KEY
CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED=false
CONTEXTBRIDGE_FORMATION_ALLOW_PAID=false
CONTEXTBRIDGE_FORMATION_OPENROUTER_FREE_ONLY=true
CONTEXTBRIDGE_FORMATION_OPENROUTER_DATA_COLLECTION=deny
```

`.env` is ignored by Git; it is a plaintext local credential file, not an encrypted vault. Keep
its OS access restricted and exclude it from shared archives/backups. Formation keys are distinct
from `CONTEXTBRIDGE_API_TOKEN`, which authenticates the memory service. No formation key belongs
in `.env.mcp`, an ingestion request, or a memory. The implementation never changes your `.env`.
The shared application already ignores unknown `.env` settings, but does not yet wire these adapters.

Validate your configuration **without network or model calls**:

```text
uv run python scripts/formation/provider.py
uv run python scripts/formation/provider.py --env-file .env
```

The runner reports only public configuration and whether a key is configured. Configuration
failures return `INVALID_INPUT` without rejected values. Environment variables take precedence
over the specified dotenv file. There is no default model and no automatic model/account selection.

## Provider choices

| Provider setting | Endpoint | Key |
| --- | --- | --- |
| `openrouter` | `https://openrouter.ai/api/v1`, fixed to the official origin | Required |
| `ollama` | Defaults to `http://127.0.0.1:11434/v1`; configurable loopback endpoint | Optional for local installations |
| `openai-compatible` | Explicit `CONTEXTBRIDGE_FORMATION_BASE_URL` for a Chat Completions endpoint | Required for hosted endpoints |

Choose a model actually available on that endpoint. Gemini/Anthropic native API formats are not
implemented; they require a compatible gateway or a separate adapter. There is no default model.
The user's selected `apodex/apodex-1.1-mini:free` was tested on synthetic data on 11 October 2026.
Its Novita route rejected `json_schema`; `json_object` worked for some cases but failed the initial
reliability probe. See the [actual verification report](../../evaluation/formation/openrouter-live-report.md).

OpenRouter free mode requires an explicit `:free` model ID for both extraction and verification.
It disables provider fallback and requests zero prompt/completion/request prices, supported
parameters and `data_collection=deny`. If no eligible endpoint exists, it fails safely; it never
silently selects a paid model or relaxes privacy. Free availability and structured-output support
vary by model. See [free variants](https://openrouter.ai/docs/guides/routing/model-variants/free),
[structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs) and
[routing preferences](https://openrouter.ai/docs/guides/routing/provider-selection).
These requests are routing constraints, not an independent guarantee of third-party retention.

Local example settings:

```dotenv
CONTEXTBRIDGE_FORMATION_PROVIDER=ollama
CONTEXTBRIDGE_FORMATION_MODEL=YOUR_INSTALLED_MODEL
CONTEXTBRIDGE_FORMATION_BASE_URL=http://127.0.0.1:11434/v1
CONTEXTBRIDGE_FORMATION_API_KEY=
```

## Opt-in execution and limits

Reading configuration never calls the network. To send an explicitly selected CapturedEvent to a
hosted provider, the operator must set `CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED=true` and use
`--execute`. This is consent to send that file to the configured provider. Use synthetic data until
privacy and evaluation approval are recorded. The user explicitly authorized the synthetic free-model
verification in the linked report; this does not authorize other providers, paid calls or private data.

```text
uv run python scripts/formation/provider.py --event docs/team-plan/fixtures/captured-event.json --execute
```

This prints proposals and admission decisions against an explicitly labelled empty comparison
snapshot. It never stores memory or calls the API/database. Actual production admission needs an
authorized event reader and a fresh injected ComparisonContext from the shared engine.

Paid/unknown-price hosted providers are blocked unless `CONTEXTBRIDGE_FORMATION_ALLOW_PAID=true`;
paid OpenRouter models also require `CONTEXTBRIDGE_FORMATION_OPENROUTER_FREE_ONLY=false`.
Only the operator can opt in. No paid provider/model/budget has been chosen or used for this work.
There is **no general currency spending-cap enforcement** in this adapter: set a hard limit with
the provider before paid use. Token limits and timeouts are not currency budgets.

Other settings:

| Setting suffix after `CONTEXTBRIDGE_FORMATION_` | Default | Meaning |
| --- | --- | --- |
| `VERIFIER_MODEL` | Selected extraction model | Separate verification request; may choose a different model on the same endpoint |
| `TIMEOUT_SECONDS` | `30` | Per-operation timeout and elapsed-response deadline; allowed range 1–120 seconds |
| `MAX_OUTPUT_TOKENS` | `8192` | Per-call output bound; allowed range 128–16384 |
| `RESPONSE_FORMAT` | `json_schema` | `json_schema` or `json_object`; local strict validation always applies |

Extraction uses a private closed JSON schema (condition pairs become the unchanged V1 dictionary).
JSON-object mode includes that same schema in the trusted system prompt and keeps local strict
validation; providers do not receive a schema through the JSON-object response-format parameter.
Verification checks semantic support with a separate prompt/call; using the same model twice is not
independent human truth. At most 100 proposals are allowed. The runner can make one extraction call
and two verification calls per proposal (extraction plus admission); it does not retry automatically.
Truncation/refusal/tool output, invalid JSON/types/provenance or recognized secrets fail safely.
HTTP 429/5xx and transport errors are retryable `PROVIDER_UNAVAILABLE`; other HTTP failures are
non-retryable. No raw provider exception/body or token is returned in failures.

Requests are limited to 256,000 bytes, decoded responses to 2,100,000 bytes. HTTPS is required for
remote endpoints; HTTP is permitted only for loopback. URL credentials/query/fragment are rejected,
redirects are disabled, and ambient proxy settings are ignored. Endpoint selection is trusted local
operator configuration, not a URL accepted from public requests. Keys use `SecretStr`, are excluded
from serialization, and are sent only as an authorization header. Known-key echoes and the existing
non-exhaustive secret detector reject credential-bearing inputs/outputs.

`ChatClient.last_observation` exposes the last completed transport's observed model, latency,
tokens and OpenRouter-reported USD cost where available; missing values remain null. Create a
separate client per processing task; do not share its observation slot between concurrent users.
Transport tests and recorded semantic verdicts establish protocol/error behavior only. Real-provider
measurements are now available for the selected free model; independent reviewed labels, an approved
quality baseline and targets, and the O3 quality gate remain pending. The observed model is not
recommended as the production default.

The user's subsequent Gemma selection also failed availability checks on the fixed tuning set;
see the [Gemma attempt report](../../evaluation/formation/gemma-baseline-report.md). Its key
authenticated, but sampled calls returned HTTP 429. No reliable production model is established.
Pranit is assigned to the independent [label/convention/target review](o3-review-request.md).
The free-model measurement runner now saves requested/observed model IDs and safe per-call
latency/usage/cost to a run-hash-bound telemetry sidecar; unknown values remain null.
