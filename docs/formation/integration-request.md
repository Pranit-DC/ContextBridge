# Formation integration requests for Pranit

## PR #29 review correction — 13 October 2026

The [review-fix report](../../evaluation/formation/groq-120b-review-fix-20261013.md) addresses your
speculative occurrence finding. Local EVENT/time corrections and audit overrides now require a
complete cited message with a bounded named subject and affirmative finite predicate; unconfirmed
completion wording is not projected. Extraction/direct admission/shared-engine no-write regressions
cover every reported form. The positive-event/date path and historical replay cases are preserved.

[Corrected explanatory copies](../../evaluation/formation/groq-120b-review-corrected-20261013/README.md)
identify direct user cache decisions and user-sourced current status. Original evidence/annotations
are unchanged; support/match/admission judgements and scores remain provisional pending your exact
acceptance. No shared contract, dependency or provider behavior change is requested. Shared factory,
account-wide quotas and BYOK UI remain your assigned work; formation still never owns persistence.

## Latest grounded handoff — 12 October 2026

Om's follow-up from latest `develop` at `c784673` prepares all requested implementation and review
material together without waiting for another approval. Groq remains `openai/gpt-oss-120b`, BYOK,
synthetic-only, sequential and free-plan-attested. See [grounded composition](grounded-quality.md),
[actual measurements](../../evaluation/formation/groq-120b-grounded-report-20261012.md) and
[one-pass review](../../evaluation/formation/groq-120b-review-20261012/README.md).

New injected `GroundedProvider`, `BatchVerifier` and `BoundedDuplicateVerifier` retain common V1
dictionaries. `QuotaClient` is now reusable formation source with shared task-local gates/budgets,
numeric-only observed-token estimates, serialization and safe failure stop. The optional batch
hook is formation-local, validates every candidate's provenance before auditing and never creates
a new contract or store. Current-state/explicit-occurrence corrections preserve source text and
copy only source-proved category/time. Generic uncertain or contradictory evidence still abstains.

New actual case P95 is 23.81 seconds on the broad fresh holdout and 20.92 on the two-case focused
holdout; costs remain unknown. Raw category/time errors, corrected offline replays and focused live
outputs are separate. Proposed judgements/scores are ready but not claimed as human-reviewed
accuracy; all pending/completed-review boundary checks remain. Historical accepted decisions are
rescored separately. Earlier sections below retain their original delivery/approval status.

Pranit's shared requirements remain:

- Inject the new adapters with one task-local shared quota gate/call list, authorized event lookup
  and fresh owner-filtered ComparisonContext. Keep shared interpretation replay, version/deletion
  fencing, persistence and conflict decisions in the engine.
- Add account-wide/daily quota coordination, queue/cancellation policy and scoped BYOK/UI handling
  in shared application files. A checkout lease/task-local gate does not cover other applications.
  Do not silently switch to paid models or relax private-data controls.
- Review the single packet and source-based conventions in this PR. Fresh judgements remain
  proposals; formal quality targets are unchanged and not marked passed by provisional scores.

No shared contract, dependency or schema change is requested. Factory/UI/worker changes belong to
Pranit; Om continues independently using injected providers and actual-engine tests with fixtures.

## Current Groq handoff — 12 October 2026

The user selected Groq `openai/gpt-oss-120b` and reported in-person Pranit/Harshal agreement
on conventions and targets. See [Groq implementation](groq-120b.md) and the
[approval provenance](../../evaluation/formation/o3-quality-targets-approved-20261012.json).
All subsequent live evaluation uses 120b, fixed synthetic inputs and BYOK. Fresh model outputs
require Pranit's review; the account's free-plan attestation is not verified provider billing.
The older sections below preserve their historical delivery/approval status.

Om now supplies `ChatDuplicateVerifier`, `ChatGroupingProvider` and
`ChatConsolidationVerifier`, plus opt-in v3 prompts/condition-key aliases. Defaults remain injected;
no common contract, shared settings/factory, API, worker, viewer, migration or dependency changed.
The module never persists content or chooses a winning conflict. Actual PostgreSQL tests through
the shared service confirm update/forget fencing with the new HTTP adapters using fixtures.

Pranit's remaining shared work:

- Wire authorized original-event lookup, fresh owner-filtered ComparisonContext and the optional
  adapters into the service/worker composition root. Keep one task-local observation client.
- Add production account-wide concurrency, token/rate limits, cancellation and bounded retries.
  Om's synthetic runner coordinates one checkout/run only; other clients can still trigger 429.
  Never silently fall back to a paid model, retry auth/quota errors immediately or relax privacy.
- Preserve interpretation replay, source rechecks, expected versions, deletion fencing and all
  conflict/persistence decisions in the engine. Canonicalize future candidate keys only after
  the agreed mapping; historical stored conditions are not rewritten by Om.
- Complete scoped BYOK handling and any viewer configuration boundary with Harshal. These are
  per-installation `.env` settings, not a hosted per-user secret vault or public credential API.
- Review new O3/O4 synthetic output packets. O3 has previously accepted gold labels; the new
  output judgements and O4 design labels are not automatically human-approved. Approving
  configuration/conventions does not establish production semantic quality.

No paid/private-data behavior is requested. Groq unknown cost is null; a free-plan confirmation
does not provide a request-level pricing/retention guarantee. Meaningful quality rates remain
unmeasured until per-candidate judgements are supplied. The user also reported in-person approval
of the new outputs; no completed judgements were supplied. The frozen holdout exposes condition,
type and scope follow-ups, and quota waits fail the approved 30-second case-latency target.
Production quality is not approved by this implementation.

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

O4 human/team review and actual semantic grouping/verification remain pending alongside O3's reliable
baseline, remaining team agreement and quality targets. Pranit accepted O3's annotations and endorsed
conventions from his side; this does not approve the production consolidation provider.
No private transcript, paid provider, API key change or hosted request was used for O4.

Contract version: 1. No common-contract change or new dependency requested for O1.

## O3 accepted annotations and remaining team decisions

Pranit accepted all 24 dataset labels and seven output judgements and endorsed the condition/key
and bounded semantic-duplicate conventions from his side in the
[formal review](https://github.com/Pranit-DC/ContextBridge/pull/23#pullrequestreview-5484764979).
The annotations were agent-assisted and explicitly accepted, not unaided independently authored
labels. Separate hash-bound completed packets are preserved with
[immutable provenance](../../evaluation/formation/pranit-reviewed-20261012/source.json).
The original pending packets remain blank. Om/Harshal agreement, a usable baseline, production
quality and targets remain pending; no shared contract or persistence change is requested here.
See [review follow-ups](o3-review-request.md) and the
[reconciliation report](../../evaluation/formation/o3-review-reconciliation-report.md).

The offline scorer now accepts `--telemetry` and validates canonical dataset/run hashes, case/call
identity and execution consistency before reporting attempts. Sequential Apodex has 1 completed
network case, 1 attempted failed network case, 9 unattempted/provider-stop cases and 1 local-only
case. Recall stays 1/10; all missed expected claims remain in its denominator. `failed_cases`
is retained only as an explicitly labelled alias for cases with an error code. Historical execution
without sufficient sidecar evidence remains unknown. See [offline usage](evaluation.md).

The [Gemma tuning attempt](../../evaluation/formation/gemma-baseline-report.md) failed all 11
network cases; sampled diagnostics returned HTTP 429 while the key still authenticated and daily
free quota remained. A single alternative free-model probe also failed availability. No reliable
model has been selected as a production default. Privacy routing/zero-price bounds and both
ignored `.env` files were preserved. No tuning or new holdout run was performed without the
required usable baseline and target agreement. No paid/private-data behavior is requested here.

The free-model runner now emits a run-hash-bound telemetry sidecar with case/stage, requested and
provider-reported model IDs, safe error/retryability, actual elapsed time and available usage/cost.
Unknowns are null. Preserve that distinction in shared observability: HTTP completion success is
separate from validated extraction/admission and never implies a persisted fact.

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
or persistence behavior was changed. Pranit accepted the quality labels; remaining team agreement,
production quality and targets remain pending. The uncertain unit qualifier is another observed
quality follow-up. Implementing these policies or live tuning is not a blocker for the scoped
review-tooling PR once its execution reporting and develop reconciliation are validated.

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

Pranit accepted O3 labels/outputs and endorsed the proposed conventions from his side. Condition-key
canonicalization and paraphrase duplicate detection still require Om/Harshal agreement; quality
targets are not approved. See [Apodex test plan](apodex-test-plan.md).

The team must select a model provider and a semantic evidence verifier for budget, privacy,
language and hardware before production O3 approval. The observed free model failed reliability;
no paid provider selection or private-data submission was authorized. Pranit owns shared configuration,
dependency or lockfile change. Proposed provider interfaces are local formation internals, not
changes to common contracts. Real implementations must bound calls and check semantic support,
atomicity, conditions, scope, dates and adoption, rather than trust excerpt matching or confidence.

## Checks that remain pending

- Production event-lookup/provider wiring, workers, and real-provider retry/failure checks.
- A reliable real model, remaining team convention agreement, an approved quality baseline and targets.
- Production consolidation grouping/verification and team review (O4); local proposal and actual
  PostgreSQL freshness/forget regressions are prepared with synthetic providers.

## Recorded P2 integration

The native Windows/PostgreSQL 18 full suite passed with zero skips on 11 October 2026, including
formation-to-P2 writes, repeat processing, admission rejection/deferral, and forgetting cleanup.
The test providers and evidence labels were recorded fixtures. These tests do not establish
production provider wiring, semantic model quality, or worker/consolidation behavior.

The O1 unit suite and sample runner use recorded synthetic fixtures. Their passing results show
contract/error/policy behavior only, not semantic model quality or a functioning end-to-end worker.
