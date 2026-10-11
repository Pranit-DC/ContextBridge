# Formation integration requests for Pranit

## O4 handoff: implementation prepared, actual provider approval pending

`formation.Consolidator(provider, verifier).propose(records)` now returns the unchanged V1 proposals.
See [consolidation usage](consolidation.md). It uses exact scope/project/conditions partitioning,
complete extractive claims, deduplicated source refs, every supporting version ID and deterministic
proposal IDs. Singleton/contested/uncertain/unsupported/overlong groups remain atomic. Same-key
different content abstains without asserting a contradiction. It never mutates memory or conflicts.

Pranit: the existing ConsolidationService and ModuleGateway already accept this entry point.
The new formation integration tests use that service with actual PostgreSQL and injected synthetic
grouping/verifier substitutes; updates and forget races are fenced by your service, not Om.
No failing shared-engine defect was identified by these tests. Please review the handoff and supply
only authorized owner-filtered live records; the V1 MemoryRecord has no developer ID for Om to verify.
Preserve source fingerprints, exact conditions, saved proposal replay, transactional source rechecks
and derived-source cleanup. Successful empty proposals mean abstention and must create no memory.

Production factory wiring needs a `GroupingProvider.group(records)` and a separate
`ConsolidationVerifier.verify(proposal, records)`. These are formation-local injected interfaces,
not common contract changes. RecordedGroupingProvider/RecordedConsolidationVerifier are test-only
design labels and must never become production defaults. The existing ChatProvider extraction
schema does not implement these consolidation interfaces; do not treat it as a working consolidator.
Pranit's shared settings/factory/docs updates remain with Pranit. Om added no dependencies/settings.

Human/team review and actual semantic grouping/verification remain pending alongside O3's reliable
baseline, condition-key/duplicate conventions and quality targets. User assignment names Pranit as
the independent O3 reviewer; this handoff does not record his approval or contact him automatically.
No private transcript, paid provider, API key change or hosted request was used for O4.

Contract version: 1. No common-contract change or new dependency requested for O1.

## User-selected provider/model/key handoff

The user approved configurable provider/model selection and bring-your-own-key setup. Om's
[local settings and runner](provider-configuration.md) use `CONTEXTBRIDGE_FORMATION_*` variables
in `.env`, the installed Pydantic/settings/httpx dependencies, and injectable Chat Completions
extraction/verification adapters. Settings inspection makes no network calls. The user's key
was detected locally without display. The user later selected the documented free-model configuration
and explicitly requested real verification. The [live report](../../evaluation/formation/openrouter-live-report.md)
records synthetic-only measurements; key presence alone remains insufficient permission for model calls.

Pranit: wire this configuration through the service/worker composition root. Supply one client
per processing task, the authorized retained-event reader and fresh ComparisonContext, and reuse
saved extraction interpretations. Keep keys outside ingestion, candidates, database rows, job
metadata, logs and responses. Preserve safe provider failure codes and all engine/deletion fences.
No shared `Settings`, `.env.example`, Compose, worker, API or dependency file was edited by Om.

Harshal/Pranit: any viewer settings screen must use an owner-authorized shared configuration
boundary, mask keys, avoid global Streamlit caches, and distinguish the memory-service bearer
token from a formation provider key. The present V1 remains a single configured developer;
per-user accounts, browser credential persistence and a hosted secret vault are not implemented.

Local operator configuration can select OpenRouter free variants, a loopback Ollama compatibility
endpoint, or an explicit Chat Completions-compatible endpoint. Free-only OpenRouter requests use
zero pricing bounds and no provider fallback. Hosted sends/paid sends require separate opt-ins;
there is no general currency cap, so paid use needs a provider-side hard limit and an approved
evaluation budget. The authorized probe used `apodex/apodex-1.1-mini:free` only with synthetic data.
Default data-collection routing is `deny`; absence of an eligible endpoint must fail without
silently relaxing it. That model's Novita route rejects `json_schema`; `json_object` is available,
but 14 of 24 initial cases failed. Do not select it as the production default from these results.
JSON-object mode now receives the trusted wire schema in its prompt. Required source validation stays.

Pranit/Harshal: the holdout runtime proposal generated `project_version` where the existing label uses
`version`; consumers require exact shared condition keys. The tuning duplicate was admitted against an
expected rejection because a paraphrase/new claim key escaped the exact comparison. These are observed
handoff defects, not authorization to change common contracts or mutation policy. Review a common
condition/key convention and the shared relation interpreter before production use. No shared file
or persistence behavior was changed. Human-reviewed quality labels and targets remain pending.

## O3 preparation and pending provider work

The user originally requested dataset preparation only and subsequently authorized the specific
synthetic free-model verification above. Do not infer permission to call a paid provider or
send private data from `.env` credentials. The [evaluation workflow](evaluation.md) supplies
separate synthetic tuning/holdout inputs, fixed fingerprints and independent-annotation scoring.
No shared settings/dependencies/contracts or production provider defaults were added.

Before real O3 execution, agree provider/model/verifier, budget, privacy and resources with the
team. Pranit owns externally configurable model/base URL/timeout settings and any new dependency.
Real calls must remain bounded, tool-free, source-grounded and safely classified on refusal,
timeout/malformed output. Preserve saved extraction/ID replay through the shared engine.

Supply safe per-case observed model/prompt/configuration, latency, token counts and cost or explicit
nulls, and separate generated proposals from accepted memory decisions. The offline scorer neither
calls providers nor authenticates externally supplied run provenance. Review labels independently,
record an approved baseline, then agree targets before tuning. Holdout must remain fixed.

The complete real-provider quality gate and production O4 provider wiring remain pending; recorded self-check
counts are not a substitute. No private-data submission or provider purchase is requested here.

## O2 admission handoff

O2 keeps the V1 entry point and reason vocabulary unchanged. See [admission policy](admission.md)
and the [29 synthetic design-labelled cases](../../evaluation/formation/admission-cases.json).
Expanded examples are available from `scripts/formation/check_admission.py:load_examples` for
team tests; labels still require team review and are not semantic model measurements.

- Treat `ADMIT` as eligibility only. Supply a real relation interpreter before proposing UPDATE
  or LINK_CONFLICT. The default engine deliberately defers related corrections without one.
- Recheck expected versions and out-of-order effective dates after admission. A supported
  backdated correction may pass admission and still require engine DEFER/AMBIGUOUS_TIME.
- Keep different scope/condition records separate. Exact duplicate rejection requires clear
  current applicability at candidate and snapshot times and no later creation/recording time.
- Preserve contested state when interpreting repeated claims. Admission of contested exact
  content does not resolve it; the default engine's exact NOOP retains it.
- Missing evidence/provider failures remain DEFER. Coherent but conflicting candidate/event
  scope bindings are DEFER/AMBIGUOUS_SCOPE, while malformed contract data fails safely.

Om's PostgreSQL tests exercise these handoffs with recorded extraction/evidence/relation providers.
Actual semantic provider and production event-reader wiring remain pending. No shared-file edit,
provider purchase, private-data submission or persistence implementation is requested by O2.

## Wiring requested

- Inject `formation.Extractor` and the initial `formation.AdmissionPolicy` through the shared
  engine. Keep `extract(event)` and `assess(candidate, ComparisonContext)` dictionary boundaries.
- Supply an authorized event reader to admission's `event_lookup(event_id)`. It must enforce
  configured developer/project binding and retention. Missing/expired/deleted evidence must not
  become successful admission. The module has no separate memory store.
- Supply fresh ComparisonContext records and recheck scope, source/evidence, effective time,
  expected versions and cancellation/deletion state immediately before committing. Admission
  does not resolve conflicts, write versions, or prevent a race with forgetting by itself.
- Reuse P2's saved extraction results and stable candidate IDs once per event.
  Provider determinism is not an exactly-once guarantee; do not silently reinterpret retries.
- Unsupported/uncertain extraction output raises safe `INVALID_PROVIDER_OUTPUT`; distinguish it
  from a successfully empty `[]` result. Provider timeout/connection failure raises retryable
  `PROVIDER_UNAVAILABLE`. Admission maps unavailable verification to DEFER/PROVIDER_UNAVAILABLE.
  Invalid event/candidate/context input raises `INVALID_INPUT`; no raw exception text is returned.

## Production provider decision pending

The user selected `apodex/apodex-1.1-mini:free` for continued synthetic O3 evaluation on
12 October 2026, with one request at a time. This is an evaluation choice, not a production-quality
approval. Om's runner now serializes extraction/verification, spaces starts, bounds total calls and
stops network work after a provider-unavailable failure. A checkout-wide OS lease prevents overlapping
CLI splits. Provider errors retain safe HTTP status and null unknown usage without exposing bodies.

Pranit: supply account-wide concurrency/rate limits across production workers, scoped BYOK secret
handling and safe retry/backoff/cancellation through the shared engine. Do not retry a quota/auth
failure immediately, reinterpret a saved event, fall back to paid models, or relax privacy. The runner's
local lease does not coordinate other checkouts or product users. Injection/persistence contracts
remain unchanged; no shared setting or worker implementation was edited by Om.

Pranit is the user-designated independent reviewer for O3 labels and real outputs. Condition-key
canonicalization, paraphrase duplicate detection and quality targets still require team agreement;
Om has not approved them on Pranit's behalf. See [Apodex test plan](apodex-test-plan.md).

The team must select a model provider and a semantic evidence verifier for budget, privacy,
language and hardware before production O3 approval. The observed free model failed reliability;
no paid provider selection or private-data submission was authorized. Pranit owns shared configuration,
dependency or lockfile change. Proposed provider interfaces are local formation internals, not
changes to common contracts. Real implementations must bound calls and check semantic support,
atomicity, conditions, scope, dates and adoption, rather than trust excerpt matching or confidence.

## Checks that remain pending

- Production event-lookup/provider wiring, workers, and real-provider retry/failure checks.
- A reliable real model, independent reviewed labels, an approved quality baseline and agreed targets.
- Production consolidation grouping/verification and team review (O4); local proposal and actual
  PostgreSQL freshness/forget regressions are prepared with synthetic providers.

## Recorded P2 integration

The native Windows/PostgreSQL 18 full suite passed with zero skips on 11 October 2026, including
formation-to-P2 writes, repeat processing, admission rejection/deferral, and forgetting cleanup.
The test providers and evidence labels were recorded fixtures. These tests do not establish
production provider wiring, semantic model quality, or worker/consolidation behavior.

The O1 unit suite and sample runner use recorded synthetic fixtures. Their passing results show
contract/error/policy behavior only, not semantic model quality or a functioning end-to-end worker.
