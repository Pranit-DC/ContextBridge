# V1 integration and checks

This branch connects the existing formation, retrieval and background modules. It does not
claim completed V1 or measured model quality until the lifecycle, viewer and final demo checks land.

## Online providers

Credentials alone do not enable capture processing. Set `CONTEXTBRIDGE_FORMATION_ENABLED=true`
and retain the formation settings selected for PR #29:

```dotenv
CONTEXTBRIDGE_FORMATION_PROVIDER=openai-compatible
CONTEXTBRIDGE_FORMATION_BASE_URL=https://api.groq.com/openai/v1
CONTEXTBRIDGE_FORMATION_MODEL=openai/gpt-oss-120b
CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED=true
CONTEXTBRIDGE_FORMATION_ALLOW_PAID=false
CONTEXTBRIDGE_FORMATION_GROQ_FREE_PLAN_CONFIRMED=true
```

Supply `CONTEXTBRIDGE_FORMATION_API_KEY` privately. The built-in runtime uses the same selected
model for extraction, evidence checks, duplicates, conflict proposals and consolidation. It caps
output at 1024 tokens. Larger inputs/outputs can defer or fail safely; evidence is never truncated
to make a request fit. Keep the existing four Cloudflare embedding settings. No model runs locally.
The Free-plan setting is operator attestation, not an API-verified billing guarantee.

Run migrations, then `docker compose --profile workers up --build -d`. Capture requires an explicit
project binding. Enabling processing can process already-buffered events in that binding; review
your installation before enabling it. Validation uses a separate `_test` database and synthetic
imports only. Neither startup nor readiness calls a model.

Each API search and worker execution constructs fresh provider state. The factory interface stays
available, and supplied backends are preserved. Unsupported and uncertain source-bound proposals
pass through admission in the built-in runtime; admission rejects or defers them before writes.

The PostgreSQL `provider_quotas` table contains an irreversible account-key hash and numeric usage
only. A separate account advisory lock serializes hosted Groq calls across processes without holding
memory locks. Reservations commit before network calls and survive process crashes. Successful usage
refunds conservative reservations; absent usage retains them. Defaults cap 8000 tokens per rolling
61 seconds, 50000 per rolling day, and space requests by 3.1 seconds. Provider/account limits can be
lower. Auth failures pause the account for 15 minutes; provider/quota failures pause it for 61 seconds.
Capacity exhaustion returns a safe unavailable result instead of sleeping inside a worker lease.
Workers use the existing bounded retry policy. Searches preserve uncertainty/degradation warnings.

Conflict interpretation proposes only. It requires a cited corrective instruction before proposing
an update; a newer incompatible statement produces a conflict or uncertainty. Scope, conditions,
expected versions and live targets are still checked by the engine at commit. Semantic comparisons
include keyless explicit saves in the same scope/type/conditions; a shared key is not semantic proof.

Built-in retrieval enables one-hop graph expansion into spare slots and selective decision evidence
checks. The response remains the existing V1 cards and warnings. A verification label reports support
by stored evidence, never independent truth. General retrieval accuracy remains unmeasured.

## Validation ledger

Ordinary tests use substitutes and never call live credentials. This implementation's live verification
budget is **40 Groq and 20 Cloudflare synthetic requests total**, sequential, with no automatic retries
and a stop on the first provider/quota failure. Calls and remaining budgets must be recorded before
claiming an actual model demo passed. Windows Docker Desktop and actual supported-host checks are
separate from protocol/subprocess tests.

Provider-stage verification: full PostgreSQL/Redis suite **1229 passed, no skips**, plus two focused
keyless-save/uncertainty checks passed. Ruff lint/format, frozen all-extras installation dry run,
Compose validation and schema-drift check passed. No live provider calls were made in this stage.
