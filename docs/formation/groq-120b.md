# Groq `openai/gpt-oss-120b` formation implementation

The user selected this model for the remaining O3/O4 work. All execution after that selection
uses `openai/gpt-oss-120b`; earlier comparison attempts are retained as historical evidence.
The provider remains configurable and uses the operator's own key (BYOK). These injected
formation adapters propose content; the shared engine owns every persistent write and conflict.

## Local settings

Place the key in the existing ignored `.env` beside `README.md`. Keep other database/API values.
Neither `.env` nor `.env.mcp` is edited by the implementation or committed to Git.

```dotenv
CONTEXTBRIDGE_FORMATION_PROVIDER=openai-compatible
CONTEXTBRIDGE_FORMATION_MODEL=openai/gpt-oss-120b
CONTEXTBRIDGE_FORMATION_VERIFIER_MODEL=openai/gpt-oss-120b
CONTEXTBRIDGE_FORMATION_BASE_URL=https://api.groq.com/openai/v1
CONTEXTBRIDGE_FORMATION_API_KEY=YOUR_GROQ_API_KEY
CONTEXTBRIDGE_FORMATION_TIMEOUT_SECONDS=30
CONTEXTBRIDGE_FORMATION_MAX_OUTPUT_TOKENS=2048
CONTEXTBRIDGE_FORMATION_RESPONSE_FORMAT=json_schema
CONTEXTBRIDGE_FORMATION_GROQ_REASONING_EFFORT=low
CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED=false
CONTEXTBRIDGE_FORMATION_ALLOW_PAID=false
CONTEXTBRIDGE_FORMATION_GROQ_FREE_PLAN_CONFIRMED=false
```

Keep hosted execution disabled for configuration inspection. After confirming the account uses
the free plan, `--execute --confirm-free-plan` on the synthetic runners supplies process-only
consent. Direct application use needs deliberate `ALLOW_HOSTED=true` and
`GROQ_FREE_PLAN_CONFIRMED=true`. This attestation does not query billing or guarantee a zero-price
route; Groq has no OpenRouter-style request pricing restriction. No paid plan or private transcript
is authorized by this evaluation. OpenRouter routing/data-collection settings do not control Groq.

Groq receives `max_completion_tokens`, strict JSON schema, `reasoning_effort=low` and
`include_reasoning=false`. Unknown cost remains null, even if a compatible envelope supplies
`usage.cost=0`. See the official [compatibility guide](https://console.groq.com/docs/openai),
[structured output guide](https://console.groq.com/docs/structured-outputs) and
[API reference](https://console.groq.com/docs/api-reference).
Groq's [data controls](https://console.groq.com/docs/your-data) are account settings, not implemented
request-level retention controls. Synthetic examples are the only inputs used here.

## Entry points and conventions

`Extractor(provider, verifier).extract(event)` and
`AdmissionPolicy(verifier, authorized_event_lookup, duplicate_verifier=...).assess(candidate, context)`
keep their existing dictionaries and injected `ComparisonContext`. `ConventionalProvider` and
`ConventionalVerifier` select prompt `formation-chat-v3-approved-conventions` for evaluation.
The optional alias map changes only explicit keys (`project_version` to `version`); it never
invents missing values or rewrites stored records. It rejects conflicting aliases.

`ChatDuplicateVerifier` compares at most 20 eligible clear/current/ACTIVE records with exact
scope, project, type, conditions and effective-time visibility. Exact duplicates still reject
locally. Paraphrased equivalents reject; uncertain comparisons defer; different claims remain
eligible for normal assessment. Unavailability defers. No winning correction or conflict mutation
is selected. Production injection must receive owner-authorized records from the shared engine.

`Consolidator(ChatGroupingProvider(client), ChatConsolidationVerifier(client)).propose(records)`
uses exact scope/project/condition buckets. Model groups must cover supplied versions exactly
once or explicitly abstain. The local renderer retains complete source claims, rare details and
all citations; it accepts no model-generated summary text. Unsupported, ambiguous, contradictory,
contested or overlong groups remain atomic. The engine still rechecks versions and forgetting
before any commit. HTTP fixtures plus actual PostgreSQL regressions exercise that path.

The user reported in-person Pranit/Harshal approval of conventions and the proposed targets.
The [approval record](../../evaluation/formation/o3-quality-targets-approved-20261012.json) identifies
that provenance without claiming an externally authenticated review. Fresh Groq predictions
still require independent human review. Targets are fixed for this experiment; changing them
after a failure cannot turn this result into a pass.

## Sequential bounded evaluation

```text
uv run python -m scripts.formation.verify_groq --model openai/gpt-oss-120b --split tuning --output evaluation/formation/NEW-tuning.json --execute --confirm-free-plan --approved-conventions
uv run python -m scripts.formation.verify_groq --model openai/gpt-oss-120b --split holdout --output evaluation/formation/NEW-holdout.json --execute --confirm-free-plan --approved-conventions --approved-holdout
uv run python -m scripts.formation.verify_consolidation --output evaluation/formation/NEW-consolidation.json --execute --confirm-free-plan
```

Freeze prompt, settings, targets and dataset hashes before holdout execution, and never tune
from its results. The saved [freeze record](../../evaluation/formation/groq-120b-v3-frozen-20261012.json)
documents this run. The fixed holdout was used historically and is not a newly unseen benchmark.
Outputs refuse overwrite. These scripts send only their built-in fixed synthetic inputs, never
the operator's database. They share one checkout OS lease and make one request at a time.

The local token guard reserves serialized UTF-8 bytes plus requested output and framing margin,
then releases unused reservation only when actual usage is known. Reservations are conservative
estimates, not measured tokens. Unknown usage stays reserved. Request starts are at least 3.1
seconds apart and token windows last 61 seconds. Defaults are 8,000 tokens/minute, at most
50,000 charged tokens/32 calls for O3 and 40,000/24 for O4. Lower those CLI limits for a smaller
quota; oversized requests and exhausted budgets stop safely without truncating source evidence.
Only actual network calls count as attempted executions. Later blocked cases still retain all
expected claims in recall. No automatic retry follows a provider failure.

This local guard does not coordinate other checkouts, other applications or provider-account
usage, and it is not a daily account counter. Actual provider limits remain authoritative.
Queue waits are included in case-completion latency and reported separately from observed
HTTP call latency. Thus the approved 30-second case target can fail even with fast model calls.
See [Groq rate limits](https://console.groq.com/docs/rate-limits).

O3 telemetry is hash-bound to the scored dataset/run. Offline review/scoring needs no provider
key, network or database:

```text
uv run python -m scripts.formation.review --split holdout --run evaluation/formation/NEW-holdout.json --telemetry evaluation/formation/NEW-holdout.telemetry.json --prepare --output evaluation/formation/NEW-review.json
uv run python -m scripts.formation.review --split holdout --run evaluation/formation/NEW-holdout.json --telemetry evaluation/formation/NEW-holdout.telemetry.json --review evaluation/formation/COMPLETED-review.json
```

Pranit must fill source support, matched claim, expected admission and rationale for every
proposal, approve every case label including empty/failure cases, and provide his review reference.
Missing judgements remain pending; fixture passes and structural output are not semantic accuracy.
The current implementation and remaining shared wiring are described in
[integration requests](integration-request.md).
