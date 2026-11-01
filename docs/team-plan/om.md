# Om — extraction, admission, and consolidation proposals

Your outcome: turn a conversation into useful, evidence-backed memory candidates, while rejecting
filler, unsupported guesses, and uncertain claims. You propose content; the shared engine saves it.

Read [common contracts](contracts-v1.md) and [team workflow](README.md). You can start without
Pranit's new API, Harshal's retrieval, a database, or a model subscription.

## Your files and boundaries

You own new `src/contextbridge/formation/`, `tests/formation/`, `scripts/formation/`,
`docs/formation/`, `evaluation/formation/`, and this plan. Suggested internal files are
`extractor.py`, `admission.py`, `normalization.py`, `consolidation.py`, and `providers/`.

Do not edit core API/models/schemas, migrations, MCP adapters, Compose, CI, shared test fixtures,
`pyproject.toml`, or `uv.lock`. Do not write to PostgreSQL or launch a queue worker from your module.
Put shared requirements in `docs/formation/integration-request.md` for Pranit to implement.
Use local helpers inside your test directory, not changes to `tests/conftest.py`.

## Start now without waiting

Create `feat/om-extraction-contract` from latest `develop` using the [branch steps](README.md).
Implement `Extractor.extract(event)` and `AdmissionPolicy.assess(candidate, context)` against
the agreed dictionaries. Load [captured-event.json](fixtures/captured-event.json),
[candidate.json](fixtures/candidate.json), and [admission-decision.json](fixtures/admission-decision.json).
Use a fake model returning recorded JSON, and an in-memory ComparisonContext.
Today's installed Pydantic/httpx dependencies are sufficient for the first deliverable.

## O1 — extraction format, normalization, and evidence

Local implementation prepared on `feat/om-extraction-contract-v1`: injected extractor and evidence
verifier, strict source-grounding checks, explicit transcript importer, fixture runner, and
formation tests. The initial `AdmissionPolicy.assess(candidate, ComparisonContext)` handoff is
also available with injected original-event lookup and scoped exact duplicate checks. All 286
repository tests passed with zero skips on native Windows/PostgreSQL 18, including recorded P2
formation/engine integration; lint, formatting, migrations and schema drift checks passed.
Merged to `develop` in [PR #12](https://github.com/Pranit-DC/ContextBridge/pull/12).
Production provider wiring and real provider quality remain pending. See
[formation usage](../formation/README.md) and [integration requests](../formation/integration-request.md).

Deliver:

- A provider-independent extractor with an injected model provider; a deterministic fake provider.
- Strict output validation and one reusable claim per candidate, using the six existing types.
- Scope, conditions, effective time, claim key, source excerpt, and event/message references.
- A transcript-to-CapturedEvent conversion helper for documented input formats. The caller must
  supply explicit project/session binding; actual host hook installation belongs to Pranit.
- A small sample runner and documented inputs/outputs that run without an actual agent or DB.

Acceptance: an explicit database decision produces the expected candidate with real evidence;
filler produces none; an assistant suggestion alone does not become memory; negation, file names,
conditions, and dates survive normalization. Invalid JSON/schema, unknown source message,
ambiguous scope, secrets, and oversize input fail safely. No raw transcript enters an error log.

## O2 — admission policy and comparison reasoning

Implemented on `codex/om-o2-admission`: configurable evidence-first admission, low-usefulness
rejection before the confidence gate for supported claims, explicit ambiguous-scope deferral,
and scoped exact comparisons that check snapshot visibility and effective intervals. Added
29 synthetic design-labelled scenarios, a reproducible runner and comparison handoff notes.
Recorded providers validate policy behavior; labels await team review and real model calibration
remains O3. All 333 repository tests passed with zero skips on native Windows/PostgreSQL 18,
including 121 formation tests; lint, formatting, migrations and schema drift checks passed.
PostgreSQL regression checks use the shared engine for every mutation.
Merged to `develop` in [PR #13](https://github.com/Pranit-DC/ContextBridge/pull/13).
See [recorded O2 validation](../../evaluation/formation/o2-report.md),
[admission notes](../formation/admission.md) and [evaluation inputs](../../evaluation/formation/README.md).

Deliver:

- Configurable usefulness/confidence policy returning `ADMIT`, `REJECT`, or `DEFER` with safe
  reason codes. Document feature meanings; a model confidence score is not proof of truth.
- Evidence checks and scoped duplicate checks against injected ComparisonContext records.
- Labelled examples for new useful memory, exact duplicate, explicit correction, conflicting
  guesses, differing environments, important rare facts, and uncertain time/source.
- Comparison notes for Pranit's resolution tests, without implementing database updates yourself.

Acceptance: empty/filler/unsupported claims are rejected; missing evidence or unclear scope/time
is deferred; a useful rare lesson is not discarded solely because it appears once. Same text in
different projects/conditions is not a global duplicate. A correction may be admitted, but only
Pranit's engine decides UPDATE versus conflict after checking the current stored version.

## O3 — a real configurable provider and extraction quality

PR #29 review follow-up (13 October 2026) addresses Pranit's confirmed speculative occurrence
defect from head `28b43e1` on the existing published feature branch. Local category/time proof now
requires an affirmative finite statement in the complete cited source message; could/should,
negated/no-confirmation statements and selectively positive uncertain excerpts cannot trigger the
override. Extraction, direct admission and real PostgreSQL shared-engine regressions cover the
reported cases; positive dated events and historical corrections remain valid. Latest develop
was fetched at `3b18501` without merging or modifying other members' work.
Corrected copies explain direct user cache decisions and user-sourced status; original evidence
and all judgements/rates remain unchanged and provisional. See the
[review-fix report](../../evaluation/formation/groq-120b-review-fix-20261013.md) and
[corrected packet explanations](../../evaluation/formation/groq-120b-review-corrected-20261013/README.md).
No new live model request or paid/private-data behavior is needed for this deterministic fix.
Review-fix validation passed: 1,144 full Linux all-extras tests with zero skips, including 566
formation tests; 65 native offline and 37 focused PostgreSQL checks passed. Ruff, dedicated `_test`
migrations/schema checks and downgrade/upgrade round trip passed. Credentials and historical
evidence are preserved; shared wiring/quality acceptance remain with their assigned owners.

Latest follow-up on `codex/om-formation-accuracy-latency` starts from `origin/develop` at `c784673`,
after verifying the user manually merged #27. The user requested all remaining source grounding,
latency and scoring preparation in one regular PR without waiting for Pranit's approval. No branch
or PR merge is performed. Only Groq `openai/gpt-oss-120b` is used for sequential synthetic execution.

Implemented compact evidence-bound extraction, indexed batch audit, narrow wrong-project and
uncertain-choice abstention, approved condition aliases, literal duplicate checks, and source-backed
category/time corrections without changing claim text or shared contracts. Reusable QuotaClient
and observed-token pacing retain serialization, budgets, unknown usage and provider-stop behavior.
The engine still owns persistence, conflicts, interpretation replay and version/deletion fencing.

Fresh 12-case raw holdout proposed precision/recall is 9/10 with one admission error (wrong event
time); that raw result remains visible. Metadata-only replays match 10/10 under agent-proposed
judgements and are explicitly not new live tests. Two further fresh live status/event cases match
2/2 after one local source correction. Broad/focused actual P95 is 23.81/20.92 seconds, below the
30-second target for this synthetic workload; production/account-wide latency remains unproven.
All new scores keep independent human review and formal quality pending, without blocking this
implementation PR. Historical accepted human decisions are rescored separately. Pranit can review
raw outputs, corrections, proposed judgements and blank packets together in the
[one-pass packet](../../evaluation/formation/groq-120b-review-20261012/README.md).
See [actual evidence/validation](../../evaluation/formation/groq-120b-grounded-report-20261012.md),
[module composition](../formation/grounded-quality.md) and
[shared requests](../formation/integration-request.md). Historical entries below retain their
original state; this entry supersedes earlier pending implementation/latency observations.
Final validation passed: 1,111 full Linux all-extras tests with zero skips, including 533 formation
tests and actual PostgreSQL/Redis/vector/viewer/MCP checks; 53 native focused checks passed.
Ruff lint/format, dedicated `_test` migrations/schema drift passed. Credentials remain unchanged;
shared application files and other members' work were not edited.

Current work on `codex/om-groq-formation-quality` starts from latest `develop` at `4b89690`,
after the user manually merged #23. The user selected Groq `openai/gpt-oss-120b` for
implementation, reported in-person Pranit/Harshal agreement on conventions and quality targets,
and approved synthetic free-plan BYOK execution. That approval provenance is recorded explicitly;
it is not an independently authenticated external review. All further model execution uses 120b.

The adapter sends strict schema, low reasoning and Groq's completion-token parameter. Optional
injected canonical condition aliases and bounded same-scope semantic duplicate assessment preserve
the common dictionaries and leave persistence/conflict mutation to the engine. Sequential quotas
retain unknown usage reservations, stop on provider failure and distinguish unattempted cases.
The original 120b baseline and v3 tuning completed all 11 network cases plus one local-only case;
v3 corrected the tuning types/time/duplicate behavior. These observations are not human-reviewed
accuracy measurements. Prompt/configuration/targets were frozen before the fixed holdout; no
holdout-driven tuning is permitted. The user subsequently reported in-person approval of the
new outputs, but supplied no per-candidate judgements; semantic rates remain unknown. The fixed
holdout exposes condition/type/scope defects, and quota waits fail the 30-second latency target.
Production quality remains unapproved; target values were not lowered to obtain a pass.
Final checks passed: 1,054 Linux all-extras tests with zero skips, including 476 formation tests,
real PostgreSQL/vector/viewer/MCP and three Redis prefork probes. Ruff, dedicated `_test`
migrations/schema drift and credential/ownership checks passed. Disposable infrastructure was
removed and both `.env` files preserved. See the
[actual implementation report](../../evaluation/formation/groq-120b-implementation-report-20261012.md).
See [Groq implementation](../formation/groq-120b.md). Historical O3 entries below retain their
original approval/delivery state; this current entry supersedes those pending convention decisions.

PR #23 reconciliation on 12 October 2026 incorporates latest `origin/develop` at `f002076`
by the user's explicitly authorized develop-to-feature branch merge. The PR itself remains for
manual merge into `develop`. #25's runner, transport and their tests are preserved exactly,
including serialization/pacing, shared call budget, provider stop, OS lease, HTTP status and
execution sidecar. #23 retains its unique review tooling/packets, Gemma evidence and proposals.

Pranit accepted the 24 dataset labels and seven output judgements and endorsed the conventions
from his side in the [formal review](https://github.com/Pranit-DC/ContextBridge/pull/23#pullrequestreview-5484764979).
The Codex-assisted annotations and human acceptance have immutable external provenance; this
does not claim unaided independent authorship. Original pending packets remain unchanged;
separate completed packets and corrected offline scores are in
[`pranit-reviewed-20261012`](../../evaluation/formation/pranit-reviewed-20261012/source.json).

Offline telemetry scoring validates canonical dataset/run hashes and consistent case/call records.
Sequential Apodex correctly reports 1 completed network case, 1 attempted failure, 9 unattempted
provider-stop cases and 1 local-only case, while recall remains 1/10. Historical execution without
sufficient evidence is unknown. The legacy failure count is labelled as cases with an error code.
See [reconciliation validation](../../evaluation/formation/o3-review-reconciliation-report.md).

Reconciliation checks passed: 997 full Linux all-extras tests with zero skips, including 419
formation tests, actual PostgreSQL/vector/viewer/MCP and Redis prefork probes; 93 native focused
offline tests. Ruff, dedicated `_test` migrations/schema drift and ownership/credential checks
passed. No live provider call was needed. Disposable test infrastructure was removed.

Om/Harshal convention agreement, a reliable baseline, approved quality targets, tuning and
production quality remain pending. Duplicate admission, condition-key drift and ambiguous units
remain quality follow-ups, not formal blockers for this scoped review/reporting PR. Historical
entries below describe their original review state; the accepted review above supersedes it.

Continued Apodex testing is prepared on `codex/om-apodex-sequential-evaluation` from latest
`develop` at `83d0a80`, after the user manually merged O4 PR #24. The user selected
`apodex/apodex-1.1-mini:free` and required requests one at a time. Added an Apodex JSON-object
fixture profile for all 24 unchanged scenarios, shared serialization/spacing, an OS lease against
overlapping CLI runs, a call budget and a stop after provider-unavailable errors. Safe telemetry
records actual HTTP status/model/usage and labels cases that never reached the network.

The new synthetic tuning attempt made three sequential calls: the first case completed both stages
with one validated proposal/ADMIT; the next extraction failed after HTTP 200 headers in 35.563 s.
Nine later cases were not attempted and one assistant-only case was handled locally. The key's
quota snapshot still had 15 requests remaining; daily quota exhaustion is not an established cause.
Whole-run token/cost totals are unknown because the failed call returned no usage. `.env` files,
prompt and datasets were preserved; no paid/private-data request, persistence or merge was used.
See [test plan](../formation/apodex-test-plan.md) and
[actual report](../../evaluation/formation/apodex-sequential-report.md).

Pranit is the user-designated independent reviewer. Review packets, condition-key/duplicate
conventions and proposed quality targets in draft PR #23 remain pending. This follow-up reuses
its safe transport telemetry fixes without merging its branch; it does not complete O3 or select
a production default. Holdout/tuning remain pending review, baseline reliability and target approval.
All 934 repository tests passed with zero skips on Docker Desktop Linux, including 356 formation
tests, real PostgreSQL/Redis prefork probes, vector and viewer checks. Native focused tests: 100
passed. Ruff, dedicated `_test` migrations/schema drift and artifact/credential screening passed;
see the linked report. Disposable test infrastructure was cleaned up. All merges remain with the user.

User-configuration implementation prepared on `codex/om-user-configurable-provider` from
`develop` at `a093059` after the dataset and other teammates' PRs merged. The user requested
provider/model selection and their own key. Added formation-local `.env` settings, an injected
bounded Chat Completions adapter, separate semantic verification calls and a configuration-check/
proposal-only runner. OpenRouter free-only routing, loopback Ollama and explicitly configured
compatible endpoints are available locally. No shared files, credentials or contracts changed.
Service/worker/viewer wiring is requested in [integration requests](../formation/integration-request.md).
The user subsequently authorized synthetic-only verification of their configured free OpenRouter model.
The selected `apodex/apodex-1.1-mini:free` rejected strict-schema responses. Added the trusted wire
schema to JSON-object prompts (version `formation-chat-v2`) without weakening validation, plus a
bounded free-model measurement runner. The two fixed splits produced 14 failed cases out of 24,
with 7 invalid-output failures and 7 unavailable-provider failures. Condition-key drift and a missed
paraphrased duplicate were also observed. This model is not ready for production; O3 remains incomplete.
Saved synthetic proposals are untrusted evaluation artifacts, never stored project facts. No private
data, paid model or merge was used. `.env` was preserved; execution overrides were process-only.
Independent reviewed labels, an approved baseline and quality targets remain pending.
See the [actual live report](../../evaluation/formation/openrouter-live-report.md).
See [configuration instructions](../formation/provider-configuration.md).
All required checks passed: 738 tests with zero skips (220 formation tests, including 69 new
cases), Ruff lint/formatting, dedicated PostgreSQL migrations and schema drift checks. Optional
viewer tests were enabled locally without manifest changes. See the
[validation report](../../evaluation/formation/provider-configuration-report.md).
This configuration PR awaits review and manual merge.
After rebasing onto latest `develop` at `23365b6` (without merging), the revised implementation passed
all 804 tests with zero skips in Docker Desktop Linux, including real Redis prefork worker probes,
dedicated PostgreSQL migrations/drift checks, viewer tests and Ruff. Native Windows passed 801 tests;
its 3 platform-specific worker skips were subsequently exercised in the full Linux run.
The live results and compatibility fix are prepared on `codex/om-provider-live-evaluation`, based
on the tested latest-develop revision. A replacement PR supersedes #20 because GitHub's rules
blocked updating its rebased branch with a force-push. The original remote branch is preserved;
all PR/branch merges remain with the user.

PR #22 subsequently merged manually into `develop`; this was confirmed at `86d93e0` before
creating `codex/om-o3-gemma-quality`. The user selected `google/gemma-4-26b-a4b-it:free` in `.env`
and asked to finish the remaining O3 gates. The key authenticated, but all 11 network tuning cases
failed with PROVIDER_UNAVAILABLE; sampled synthetic diagnostics returned HTTP 429 despite daily
quota remaining. No reliable-model or accuracy claim is made. The prompt, datasets and `.env`
were preserved; no new holdout execution or prompt tuning occurred. Per-call requested/observed
model IDs, safe failure/latency/usage/cost telemetry now export to a hash-bound sidecar, with
unknowns explicit. Safely parsed usage survives invalid generated content without accepting it.
The user assigned Pranit to independent review. Added blank evidence/context/output review packets,
an offline review-boundary scorer, proposed condition/duplicate conventions and proposed targets.
No human judgement, team agreement or approval was invented; the decisions remain pending.
The scoped follow-up passed all 815 repository tests with zero skips in Docker Desktop Linux,
including PostgreSQL migrations/drift, real Redis worker probes, vector/viewer tests and Ruff.
See the [Gemma baseline report](../../evaluation/formation/gemma-baseline-report.md) and
[Pranit review request](../formation/o3-review-request.md). O3 is still incomplete until a usable
provider, independent labels and team-approved conventions/baseline/targets enable tuning and the
fixed holdout check. All merge operations remain with the user.

Dataset preparation implemented on `codex/om-o3-provider-evaluation` from latest `develop`.
The user selected dataset preparation only and left real-provider evaluation pending. Added
12 synthetic tuning cases and 12 fixed holdout cases, with 20 expected claims covering all six
types, canonical fingerprints, source annotations and an offline scoring/fixture-check runner.
Design labels await team review. No real model was selected/downloaded/called, and no private
transcript was used. Real-provider implementation, observed baseline, configuration/latency/token/
cost records, quality targets and production integration remain pending. This does not complete O3.
All 363 repository tests passed with zero skips on native Windows/PostgreSQL 18, including
30 new evaluation tests; lint, formatting, migrations and schema drift checks passed. Both
recorded split self-checks passed. See the [preparation report](../../evaluation/formation/o3-preparation-report.md).
Dataset preparation merged in [PR #14](https://github.com/Pranit-DC/ContextBridge/pull/14).
All merge operations are left to the user.
See [evaluation workflow](../formation/evaluation.md) and [dataset manifest](../../evaluation/formation/manifest.json).

Deliver:

- One real provider behind the same interface, selected with the team for budget, privacy,
  language support, and hardware. Keep model/provider/base URL/timeout externally configurable.
  Ask Pranit to add needed settings/dependencies; do not add credentials or hard-coded secrets.
- Strict structured output, bounded input/output, timeout and safe failure classification.
  Provider calls cannot invoke database writes or privileged tools.
- Annotated extraction/admission dataset and a measured report in `evaluation/formation/`.
  Keep a tuning set separate from fixed holdout cases; use synthetic or consented redacted data.
- Record actual model ID/configuration, prompt version, latency, token usage where available,
  and observed cost; show missing cost data explicitly.

Acceptance: the real provider produces source-grounded candidates on unseen labelled examples;
timeout/malformed/refusal output becomes a safe failure or DEFER, never a successful guessed memory.
Report useful-claim precision/recall, unsupported-claim rate, and admission errors. Agree the
quality targets after recording the baseline and before tuning; fixture results are not model scores.

If a model account/budget is not ready, continue O4 and the dataset with the fake provider.
The real-provider quality gate stays pending; do not report that all extraction is finished.

## O4 — consolidation proposals and integrated regressions

Current Groq continuation supplies real injectable `ChatGroupingProvider` and
`ChatConsolidationVerifier` for the user's selected `openai/gpt-oss-120b`. Complete extractive
summaries, exact boundaries/citations, abstention and all shared-engine commit/forget fences remain.
Five new actual PostgreSQL regressions through the HTTP adapters passed with fixture responses;
they establish engine safety, not semantic model quality. Fixed synthetic live O4 evidence and
Pranit's independent output/design-label review are recorded separately. Production factory wiring
remains Pranit's task. The original real-model ambiguous-evidence group was rejected after an
O4-only evidence-prompt revision; all eight design proposal counts then matched. This is not a
human accuracy score. O3 prompts/holdout were unchanged. See
[Groq implementation](../formation/groq-120b.md).

Fixture-stage implementation prepared on `codex/om-o4-consolidation` from latest `develop`
at `86d93e0` (includes manually merged PR #22). Added the unchanged `Consolidator.propose(records)`
entry point, injected grouping/verification interfaces, exact scope/condition buckets, complete
extractive summaries and deterministic version/provenance citations. Rare details survive;
contested, unsupported/uncertain, same-key different-content and overlong groups stay atomic.
No memory/conflict mutation, common contract change, hosted request or provider purchase occurred.

The actual Om module now passes merged ConsolidationService/PostgreSQL regressions for commit,
replay, source edges, abstention, updates/forgetting during both provider stages and derived-summary
cleanup. Pranit's engine owns the source rechecks and deletion fencing. Existing formation write
regressions confirm ingestion replay and no writes on deferral. Required lint/format checks,
dedicated PostgreSQL migrations/drift checks and the all-extras Linux suite passed: 879 tests,
zero skips, including 301 formation tests and all real Redis prefork probes. Eight synthetic
design-labelled scenarios passed; these are not actual model quality scores or human approval.
See [O4 validation](../../evaluation/formation/o4-report.md),
[consolidation usage](../formation/consolidation.md) and
[shared handoff](../formation/integration-request.md).

Independent/team review and production semantic grouping/verifier/factory wiring remain pending.
O3's baseline/convention/quality gates remain incomplete; this fixture-stage O4 delivery does not
claim the full real-provider pipeline is finished. The PR targets `develop`; all merges remain
with the user.

Deliver:

- `Consolidator.propose(records)` with the agreed ConsolidationProposal shape. Consolidation
  combines related supported context into a useful summary; it does not erase original evidence.
- Same-scope/compatible-condition grouping, traceable source version IDs, and rare-fact preservation.
- Never merge contradictory claims into a confident summary. Defer or retain conflict explicitly.
- Tests for stale source versions, missing evidence, incompatible conditions, sensitive text, and
  a source forgotten while a proposal is being processed. Pranit handles commit/deletion fencing.
- On the merged service, validate the complete write path with Pranit and fix formation defects
  in your own files. Supply failing examples to other owners rather than editing their modules.

Acceptance: proposals cite all supporting versions, cannot cross projects, and preserve important
rare details. A changed/deleted source causes engine rejection or recomputation. In the real
pipeline, repeat ingestion does not duplicate memory, and deferred extraction never silently writes.

## Tests and PR sequence

Suggested separate PRs: O1 format/extractor; O2 admission; O3 provider + measured dataset;
O4 consolidation + regression fixes. Target `develop` for each one.

After creating the test directory:

```text
uv run pytest tests/formation
uv run ruff check .
uv run ruff format --check .
```

Run all [required checks](../../AGENTS.md) before review, with a dedicated `_test` database for
the repository suite. You do not need the DB for your isolated formation tests.
Use behavior-based tests: an unsupported guess must not pass just because a fake model supplied it.
Mark real provider and engine tests separately from fake-backed unit tests.

## What you hand to Pranit and Harshal

- Importable agreed entry points, example JSON, and tests; no private environment settings.
- `integration-request.md`: provider/config requirements, expected error codes, pending real checks.
- Labelled admission/correction/conflict scenarios for Pranit's engine tests.
- Your formation dataset/report for Harshal's overall evaluation. Harshal owns his benchmark
  files; do not edit his directories to add scenarios.

If the shared type package is not merged yet, keep dictionaries at the boundary. When it lands,
add a small conversion/validation change; do not rewrite your extraction algorithm. If DB wiring
is pending, continue quality data, provider failures, consolidation, and documentation.

## Prompt for your coding agent

```text
Work on Om's next unfinished phase in docs/team-plan/om.md, not other members' work.
Read AGENTS.md, README.md, docs/architecture.md, and docs/team-plan/contracts-v1.md first.
Create a focused feature branch from develop and target the PR to develop; never modify main.
Change only formation source/tests/scripts/docs/evaluation and Om's plan as assigned.
Do not edit API/models/migrations/MCP/Compose/CI/pyproject.toml/uv.lock/shared tests.
Implement agreed entry points with injected providers and ComparisonContext; use fixtures now.
Require real source evidence; do not store assistant guesses, secrets, or ambiguous scope as facts.
Propose memory and consolidation only; the shared engine owns persistence and conflict mutation.
Record shared requirements in docs/formation/integration-request.md and continue independent tasks.
Run meaningful module tests and repository checks; separate fake results from actual model quality.
Ask before changing common contracts or choosing paid/private-data provider behavior.

Do not perform any merge operation. Create the feature branch and prepare the changes and PR targeting `develop`, but do not merge the PR or merge any branches. I will review and perform all merge operations manually.
```
