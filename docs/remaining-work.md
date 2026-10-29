# ContextBridge remaining work

## Current authoritative audit — 30 October 2026

See [end-to-end status](completion-status.md) for the current 17-component audit
and remaining release gates. Older unchecked implementation claims below are
historical; they do not override the newer evidence.

- [x] Live synthetic lifecycle now passes: import, duplicate rejection, semantic
  retrieval, correction/history indexing, consolidation, restore indexing and
  cleanup. Both conflicting claims also pass live evidence checks while remaining
  uncertain. Exactly 10 Groq / 8 Cloudflare calls; the new ledger is stopped.
- [x] Implement conservative exact-claim compaction through preview/confirm API,
  preserving evidence/history and retiring affected summaries atomically.
- [x] Verify rollback, version/scope/plan fences and foreground progress while an
  injected background provider waits. This is not hosted load acceptance.
- [ ] Authorized host/session reference integration, remaining evidence/time
  contract decisions, representative model quality, independent review, promised
  host/platform walkthroughs and final stakeholder acceptance remain.

Final local verification on merged UI/benchmark base `cb58412`: **1,611 passed**,
no skips/xfails, 86% coverage; Ruff check/format, lock validation, dedicated test
migrations and schema drift check pass. Seventeen existing Alembic warnings.

See [compaction workflow](memory-compaction.md) and
[fresh live evidence](../evaluation/live/20261030-capped/README.md).

## #17 local settings and user workspace — 29 October 2026

Branch: `feat/local-settings-experience`, from develop `d332db8`.
Pranit's current request explicitly authorizes the user-facing/BYOK work; the
existing inspection UI is reused with focused presentation changes. Formation
and retrieval algorithms and common message contracts are unchanged.

- [x] Open a single local workspace without provider credentials or a running API;
  setup starts at Settings, with memory/add/activity navigation available.
- [x] Configure the supported Groq + Cloudflare stack, selected approved model,
  account ID and opt-in processing/search. Safely retain, replace or remove keys.
- [x] Keep stored keys out of public snapshots and prefilled browser fields;
  clear new keys after submission. Private atomic file updates, stale-edit
  rejection, safe configuration errors and no hidden credential backups.
- [x] Separate local save from explicit Apply; preserve memory volumes, sanitize
  inherited settings, and record applied revisions only after command success.
- [x] Add explicit single-request synthetic connection checks with cost/data
  disclosure, no retries, cooldown and persistent daily attempt ceilings.
- [x] Expose supported project, grouping, retention, consolidation and token-limit
  controls. No automatic host-hook installation or unsupported schedule editor.
- [x] Reduce clutter with task-based navigation, optional filters/source details,
  evidence-first inspection, wrapping provider cards and visible keyboard focus.
- [x] Capture five actual browser screenshots with synthetic data for the report;
  verify the 390px layout and actual save/evidence behavior.
- [x] Exercise the complete new workspace lifecycle against the real API and
  PostgreSQL. Check real Compose settings for API/worker/scheduler and two actual
  apply/recreate operations on an isolated disposable fixture.
- [ ] Independent first-time-user/accessibility review, Windows Docker Desktop
  walkthrough and actual live-provider acceptance. No actual user key/store or
  running stack was changed, and the stopped provider ledger was not resumed.

See [setup and precise boundaries](local-workspace.md),
[report gallery](report/interface-screenshots.md) and
[isolated apply evidence](report/settings-apply-verification.json).
Final verification: **1,581 passed**, no skips or xfails, 86% coverage. Ruff check,
format check (383 files), lock validation, dedicated test-database migration
upgrade and `alembic check` passed. Real Linux/Redis worker probes and MCP processes
ran. Seventeen warnings are the existing Alembic configuration deprecations.
## Offline benchmarks for #12, #14 and #16 — 29 October 2026

Branch: `feat/retrieval-quality-benchmarks`, from merged PR #43 (`d332db8`).
This section supersedes older statements that ranking/context bounds are absent.

- [x] **#12 comparison tooling:** real PostgreSQL lexical/symbolic, vector-only
  and hybrid comparison with version/scope/condition/deletion/no-match cases and
  explicit stale/missing-index degradation. Synthetic fixture vectors isolate
  integration; they do not measure an actual model's semantic quality.
- [x] **#14 comparison tooling:** fusion versus production conflict ranking,
  retaining uncertain alternatives and warning about result-limit omissions.
- [x] **#16 comparison tooling:** ranked versus compact results, UTF-8 serialized
  byte totals, long/multibyte qualified claims, total-capacity omissions and full
  source inspection. Useful selection and full-claim availability are distinct.
- [x] **Recorded execution:** 17 design cases + three scale probes × five modes
  = **100 comparisons**; all design checks pass. Five measured warm repetitions
  follow one warmup. Zero hosted requests; 0/100/500 project distractors are
  measured. Dataset/runner fingerprints and raw samples are included.
- [ ] Independent relevance review, agreed real-world targets, actual-model
  development/holdout evaluations, hosted cost/latency and larger/concurrent load
  acceptance. These gates remain open; no 100% claim for these three components.

See [method, results and repeat command](../evaluation/pipeline-benchmarks/README.md)
and [raw evidence](../evaluation/pipeline-benchmarks/offline-20261029.json).
No production policy, teammate-owned module, common message, schema, dependency
or credential configuration is changed.

Final checks: **1,569 passed**, no skips or xfails, 88% coverage. Ruff check,
format check (375 files), locked dependency validation, test-database migration
upgrade and `alembic check` passed. The 17 warnings are existing Alembic
configuration deprecations. Real Linux/Redis workers and MCP subprocess checks ran.

## Historical context, evidence review and keyless safety — 29 October 2026

Branch: `feat/memory-context-review`. PR #42's #8 implementation is now merged
into develop as `ced9a58`, with green GitHub CI; independent model/relevance-label
approval is still not inferred from that merge.

- [x] **#13 implementation:** additive `/v1/retrieval/context` and `memory_context`
  follow the authorized seed's directed supersession chain. Historical versions
  have explicit roles, status, applicability and edge endpoint IDs. Normal V1
  search continues to exclude inapplicable history.
- [x] **#15 implementation:** explicitly requested conflict checks evaluate both
  authorized claims against their evidence, with at most four requests, bounded
  account pacing and no automatic retries. Conflicts remain uncertain; no winning
  truth or new stored fact is inferred.
- [x] **Freshness and limits:** source snapshots are fenced before each check,
  after built-in quota waits and before output. Forgetting during a quota wait
  blocks the next hosted request. Size selection precedes checks; long claims
  receive omission markers rather than misleading prefixes.
- [x] **#5 known safety defect:** the hosted boundary now defers category drift
  when either property key is missing. Three ordinary regressions replace the
  former strict xfail; distinct known-property facts and capable injected
  interpreters remain supported. This is a conservative abstention fix, not
  general semantic conflict classification.
- [ ] Actual live-provider acceptance/quality, independent human review and final
  release checks remain separate gates. Tests use scripted hosted HTTP responses,
  not new live requests or a resumed stopped ledger.

Final automated verification: **1,560 passed**, no skips or xfails, 88% coverage;
Ruff check/format, lock validation, test-database migrations and schema drift check
passed. The 17 warnings are existing Alembic configuration deprecations.

See [behavior and final check record](memory-context.md). The existing viewer UI
is unchanged; these operations are available through API/MCP. No teammate-owned
formation, retrieval or inspection source is edited, and V1 message shapes stay
unchanged. No branch has been merged into main by this work.

## #8 integration completion — 29 October 2026

Branch: `feat/related-memory-links`, based on develop `b845063`.

- [x] Bring automatic reference-based links, backfill and lifecycle tests onto
  the latest develop code without losing the teammate's correctness fixes.
- [x] Resolve overlapping expansion tracking: only the newer request-local
  ContextRepository tracks fresh graph neighbors; direct matches retain priority.
- [x] Run a reproducible real-PostgreSQL direct-search/graph comparison: eight
  synthetic design cases match expectations. Two add their intended contextual
  neighbor; six controls avoid extra context (prose overlap, missing evidence,
  other project/owner, unmatched conditions, full card limit).
- [x] Supply immutable comparison output, a repeatable evaluation command and
  safe refusal of non-test/nonempty stores, with cleanup tests.
- [ ] Independent review of design-case relevance and final product-quality
  approval. This human acceptance is not inferred from passing automated checks.

The implementation and offline comparison complete #8's technical work for the
documented shared-code-reference rule. Arbitrary semantic relation inference is
explicitly excluded from this rule, not silently claimed implemented. Hosted
conflict/correction interpretation belongs to #5 and is not required to create
these deterministic links. The earlier #5 xfail is resolved by the newer safety
work described above; its original verification record remains historical.

See [implementation and final checks](related-memory-links.md),
[comparison](../evaluation/related-links/integration-comparison-20261029.json) and
[labelled design cases](../evaluation/related-links/cases.json). These are synthetic
design labels pending independent review, not approved real-world accuracy scores.
Nothing has been merged into develop or main by this work.

## Latest develop audit — 29 October 2026 (`b845063`)

This section supersedes older status statements below. Develop was pulled with
`--ff-only`. The code, new test cases and recorded verification artifacts were
inspected; this audit did not rerun tests or contact live providers.

### What the teammate delivered

- Phases 1–2 and a subsequent correctness review are merged. Group recovery,
  retention cleanup, temporal defaults, query clarification, graph depth/direct
  priority, ranking and context-budget safeguards have new regression coverage.
- Phase 4 added integrated hosted-adapter checks using mocked HTTP and real
  PostgreSQL. It added duplicate/category-drift safeguards, threshold-sensitivity
  artifacts, and extraction/state/history/consolidation/verification regressions.
- Phase 4's recorded result is **1,492 passed, four skipped, one strict xfailed**.
  The skips are Linux worker probes on Windows. The xfail is a known safety defect,
  not a completed requirement. Additional live requests were **zero**.
- Phase 3 BYOK/onboarding UI and Phase 5 benchmark deliveries were not found in
  the newly merged changes. Existing operational memory controls remain available.

### Remaining work, in priority order

1. **#5 conflict safety:** keyless cross-category claims can become two clear
   conflicting records. The hosted interpreter returns unrelated before semantic
   comparison when types differ. Resolve with the module owner or an authorized
   integration safeguard; retain a real failing regression, then remove the xfail
   only when fixed. This also affects #4 admission/duplicates and #6 state.
2. **#8 integration:** completed on `feat/related-memory-links`; current technical
   evidence is linked above. Team review/merge into develop and independent
   quality acceptance remain; no earlier branch result is substituted for current checks.
3. **#13:** explicitly labelled historical graph context is still missing. Graph
   depth/direct-priority fixes are already delivered and should not be redone.
4. **#15:** compare conflicting evidence. The current contested short circuit only
   labels uncertainty. Mocked HTTP-400 handling is now covered; real acceptance
   of the provider request remains unverified.
5. **#9:** decide/implement active-record compaction, then evaluate summary quality
   and foreground responsiveness. Current summaries preserve original active sources.
6. **#17 / Phase 3:** provider/BYOK onboarding, safe settings/key changes, explicit
   bounded connection checks and automated/human usability/accessibility coverage.
7. **#1/#3/#11 integration limits:** multi-event evidence, date/range persistence,
   per-source timezones and host/session query-reference binding still require
   coordinated contract/integration work or explicit scope exclusion.
8. **#2/#4/#5/#6/#8/#9/#12/#13/#14/#15/#16:** fresh live-provider verification,
   independently reviewed quality, and Phase 5 relevance/cost/latency/scale
   measurements remain. Threshold sensitivity is not approved calibration.
9. **Final delivery:** actual promised agents/platforms (including Claude and
   Windows Docker Desktop), independent setup walkthrough, requirements-to-test
   mapping, final-head Linux/Redis/full checks, documentation/demo and acceptance.

#7 memory records and #10 current-query input have no newly identified missing
implementation. #14 ranking and #16 byte/character context bounds are implemented;
finish their evaluation rather than rebuilding them. Byte bounds are not token counts.

Evidence: [Phase 4 report](../Docs/remaining-task-phase4.md),
[checks](../Docs/phase4-evidence/checks.json),
[Phase 2 correctness review](../Docs/reviews/phase2-correctness-20261029.md),
`ChatRelationInterpreter.compare`, and the strict xfail in
`tests/integration/test_phase4_transitions.py`. The existing live ledger is stopped;
no previous stop/budget authorizes new hosted requests by itself.


## Develop audit — 29 October 2026

This audit supersedes older implementation-status statements below where they
overlap. Local develop was fast-forwarded to `3e84ec9` (PRs #37 and #38 merged).
The five-phase assignment supplied by Pranit contains 23 tasks.

| Assigned phase | Merged status | Still for the assigned teammate |
| --- | --- | --- |
| 1: correctness, tasks 1–3 | Code fixes and regression suites present | Linux/integration confirmation on the final head |
| 2: backend, tasks 4–8 | All five bounded implementations present | Complete integration limits and quality checks, rather than claiming general support |
| 3: UI/configuration, tasks 9–11 | No new implementation/evidence found in develop | BYOK/onboarding settings, safe key/configuration handling, automated workflows |
| 4: live checks, tasks 12–18 | No new phase-completion evidence found | Current integrated real-provider checks and resulting fixes |
| 5: benchmarks, tasks 19–23 | No new phase-completion evidence found | Retrieval/graph/verification/scale/consolidation responsiveness measurements |

Phase 2 limits: relative date/range claims defer because storage requires an
instant; source timezone is configured globally rather than per source; grouped
claims citing multiple events defer; session query-reference context is injectable
but not connected to hosts; context limits are byte/character bounds, not token
counts. These limits require coordinated contract/integration work if supported.
Query understanding is bounded topic/intent heuristics, not general language
understanding. Reranking retains unresolved alternatives rather than choosing truth.

Evidence: [phase report](../Docs/remaining-task-phase2.md), actual engine modules,
new Phase 1 integration suites and Phase 2 unit/boundary tests. This audit reran
the four new engine unit suites: **56 passed**. It did not rerun PostgreSQL,
Redis/worker transport, migrations, the full suite or live providers. The report
records 1,386 passed and four Windows/Linux-transport skips for its implementation
head; this is reported prior evidence, not a fresh merged-head result.

### Work outside the teammate's five-phase assignment

- [ ] Review/approve independently labelled outputs and final model-quality gates;
  automated reports alone are not human acceptance (§2–6, §8–9, §12–16).
- [x] Implement bounded evidence-backed related_to creation (§8), on
  `codex/pranit-related-memory-links`; shared explicit code references, not general
  semantic inference. See [implementation](related-memory-links.md).
- [ ] Decide and implement or explicitly exclude labelled historical graph context (§13).
- [ ] Decide and implement or explicitly exclude active-record compaction after
  consolidation (§9); derived summaries currently preserve original active sources.
- [ ] Implement comparison of conflicting claims' evidence if required (§15);
  the five phases retest existing verification but do not explicitly implement
  this missing behavior. Contested records currently short-circuit to uncertain.
- [ ] Agree user-facing operational controls (capture, retention, scheduling,
  limits) and final configuration choices, coordinated with Phase 3 (§17).
- [ ] Complete independent installation/usability/accessibility walkthroughs and
  promised real-agent/platform checks, including Claude and Windows Docker Desktop.
- [ ] Resolve cross-event evidence, temporal precision/per-source timezone and
  host/session reference-context contract decisions with the Phase 2 implementer.
- [ ] Finish requirements-to-evidence mapping, documentation/demo, full required
  checks on the final release head and team/stakeholder acceptance.

The five phases remain with the teammate; this list is complementary work,
not authorization to take over their assigned modules or change shared contracts silently.

This is the ongoing checklist from the project completion review. Update it as each
part is discussed. All 17 components below have been reviewed; newer audit and
implementation notes supersede their earlier status where applicable.
An unlisted component is not necessarily complete. This file records work, not an
instruction to implement it automatically.

## Definition of done

Accepted by Pranit in this conversation:

- Every agreed requirement is implemented and verified, or formally removed from scope.
- The full memory lifecycle works end to end.
- Memory works across all promised agents, environments and new sessions.
- Correctness, isolation, safe updates, failures, recovery and permanent deletion are demonstrated.
- Measured extraction/retrieval quality, duplicate/conflict handling, latency and cost meet agreed targets.
- Someone outside the team can install and use the documented system.
- Final test evidence, evaluation, documentation, demo, limitations and team/stakeholder acceptance are complete.

Further improvements can follow completion of this agreed scope.

## 1. Interaction buffer

**Status: partially complete.**

### Expected behavior

Temporarily collect recent conversation turns, then process them together at a
suitable time. Preserve conversation context and avoid an expensive AI processing
run after every message.

### Already implemented

- Durable PostgreSQL storage before processing, with an event and queued job committed together.
- Caller-supplied events containing multiple messages.
- Configurable retention and capacity limits; expiry clears stored text.
- Replay handling, owner/project boundaries and restart durability.

### Remaining work

- [ ] Automatically collect related turns from the same session into a bounded group,
  preserving order, message identity and supporting evidence.
- [ ] Agree and implement when a group is ready: for example an idle timeout,
  message/size threshold or a supported session-end signal. These are proposed
  trigger choices, not a claim that every host provides a session-end event.
- [ ] Connect group readiness to the existing worker pipeline so each captured
  message does not independently trigger expensive processing before grouping.
- [ ] Preserve existing scope, retention, replay, recovery and forgetting safeguards
  when grouping; expired or forgotten messages must not be processed later.
- [ ] Verify with meaningful tests that related turns are processed together,
  sessions/projects remain separate, retries do not repeat completed work, and
  partial groups recover safely after restart.
- [ ] Record a representative comparison showing fewer processing/provider calls
  than processing each message separately, without losing required context.

### Evidence inspected

- [Ingestion implementation](../src/contextbridge/engine/ingestion.py):
  `ingest()` saves each event and creates its own job/outbox work item.
- [Buffer bounds and retention](ingestion.md#bounds-and-retention):
  multi-message event limits, temporary retention, capacity and expiry behavior.
- [Existing integration tests](../tests/integration/test_ingestion.py):
  restart, replay, isolation, capacity and expiry cases.

These sources were inspected during this review. Tests were not rerun for this
documentation update; existing tests do not prove automatic session grouping.

## 2. Candidate extraction

**Status: implemented and connected; quality acceptance incomplete.**

### Expected behavior

Turn interactions into individual reusable knowledge candidates, such as
"Project uses PostgreSQL", rather than saving a whole chat as long-term knowledge.
Candidates are proposals; admission and the shared engine decide what is stored.

### Already implemented

- Provider-backed extraction into structured candidates with type, scope,
  conditions, time and source/evidence references.
- Output validation, provenance checks and evidence-verifier integration.
- Assistant-only input returns no candidates without a model call.
- Hosted Groq extraction is connected to the shared runtime; live imports have
  produced stored knowledge. Temporary raw interactions remain subject to retention.

### Remaining work

- [ ] Complete independent review of the current extraction evaluation outputs;
  agent-proposed scores and corrected offline replays are not final quality approval.
- [ ] Demonstrate agreed quality targets on representative fresh held-out cases,
  including individual reusable claims, negation, conditions, scope, categories,
  effective dates, uncertain statements and useful information that must not be missed.
- [ ] Fix any remaining extraction defects found in that evaluation and verify
  the current integrated path with real providers. Earlier raw runs showed
  category/date errors; local corrections do not establish general model accuracy.
- [ ] Record extraction quality and processing latency/cost with clear limits,
  distinguishing raw model output, deterministic corrections and final candidates.

### Evidence inspected

- [Extractor](../src/contextbridge/formation/extractor.py): structured parsing,
  source checks, verifier integration and assistant-only short circuit.
- [Extractor tests](../tests/formation/test_extractor.py): malformed output,
  unsupported/uncertain evidence and invalid provenance coverage.
- [Grounding evaluation](../evaluation/formation/groq-120b-grounded-report-20261012.md):
  raw category/date errors, corrected replays, small fresh live checks and pending independent review.
- [Integrated verification](v1-completion.md): actual imports extracted and stored
  evidence-backed PostgreSQL decisions; general model quality remains unapproved.

Source/evaluation inspection only; tests and live models were not rerun in this review.
Duplicate admission and storage/conflict decisions will be reviewed under their
own components rather than treated as extraction alone.

## 3. Normalization

**Status: partly implemented; general temporal normalization not fully demonstrated.**

### Expected behavior

Produce clear, consistent candidates without changing meaning. Resolve relative
time such as "yesterday" only with a justified reference date/timezone; preserve
original evidence and uncertainty.

### Already implemented

- Structured candidate fields and timezone-aware timestamps normalized to UTC.
- Explicit condition-key aliases (for example project_version to version), with
  conflicting aliases rejected rather than silently combined.
- Model instructions to preserve negation, identifiers, units and evidenced time.
- Narrow source-backed category/time corrections for affirmative occurrences
  with explicit ISO timestamps. Uncertain wording cannot supply local date proof.

### Remaining work

- [ ] Specify and verify relative-time handling (yesterday, last week, etc.) using
  the correct source timestamp/timezone, without inventing an exact instant from
  a date-only statement. Define safe deferral for missing or ambiguous context.
- [ ] Demonstrate the user's "we switched to SQLite yesterday" example through
  the integrated path, with preserved meaning, source and justified effective time.
- [ ] Add meaningful coverage for timezone/day boundaries, delayed imports,
  negation, uncertain dates, aliases and preservation of units/identifiers.
- [ ] Independently review representative normalization outputs and confirm
  category/condition/time accuracy. Earlier evaluation category/date errors and
  corrected offline replays do not establish general normalization quality.

### Evidence inspected

- [Timestamp contract](../src/contextbridge/contracts/messages.py): aware input
  timestamps converted to UTC; this alone does not resolve relative language.
- [Conventions](../src/contextbridge/formation/providers/conventions.py): explicit
  aliases and meaning-preservation instructions.
- [Grounded provider](../src/contextbridge/formation/providers/grounded.py):
  bounded explicit-source metadata corrections; other wording uses semantic checks.
- [Occurrence tests](../tests/formation/test_occurrence_grounding.py): affirmative
  ISO timestamp cases and refusal to infer a date from speculative "yesterday".
- [Grounding quality notes](formation/grounded-quality.md): limits and pending review.

Tests/live providers were not rerun. Relative-time normalization may be proposed
by the model; general reliable handling is not established by the inspected evidence.

## 4. Memory admission gate

**Status: implemented and connected; admission quality acceptance incomplete.**

### Expected behavior

Keep useful supported knowledge, such as an expressed TypeScript preference,
and reject conversational filler such as "Okay, thanks". Admission produces
ADMIT, REJECT or DEFER; the shared engine still authorizes final writes.

### Already implemented

- Evidence/provenance checks, secret screening and scope/time checks.
- Unsupported claims reject; missing/uncertain evidence or unavailable verification defer.
- Supported low-usefulness candidates reject; low confidence defers. Thresholds
  are configurable, not calibrated probabilities of truth.
- Eligible exact duplicates reject; optional semantic comparison can reject
  equivalents or defer uncertainty. Comparison respects scope and applicability.
- Unit tests cover decisions, thresholds, duplicates and uncertainty; integrated
  live imports have passed through the gate into storage.

### Remaining work

- [ ] Independently review fresh admission outcomes against agreed targets,
  measuring both noisy claims admitted and useful claims incorrectly rejected/deferred.
- [ ] Demonstrate representative filler, explicit preferences, rare useful facts,
  unsupported claims and ambiguity through the current integrated real-provider path.
- [ ] Validate/calibrate usefulness and confidence thresholds against reviewed
  cases; model estimates alone do not prove useful, evidence-supported memory.
- [ ] Verify current duplicate rejection with real providers and fix any remaining
  issues. An earlier integrated live repeated statement produced duplicate memory;
  later safeguards/offline tests have not established that live failure resolved.
- [ ] Confirm fixes prevent the category/date-related incorrect admissions recorded
  in earlier raw runs; retain raw failures separately from corrected replays.

### Evidence inspected

- [Admission policy](../src/contextbridge/formation/admission.py): evidence-first
  ADMIT/REJECT/DEFER, thresholds and scoped exact/optional semantic duplicate checks.
- [Admission tests](../tests/formation/test_admission.py): policy and failure cases.
- [Grounding evaluation](../evaluation/formation/groq-120b-grounded-report-20261012.md):
  raw admission errors and pending independent quality approval.
- [Integrated report](v1-completion.md): live successful storage and repeated-statement failure.

Source/evidence inspection only; tests and live providers were not rerun for this review.

## 5. Conflict resolution

**Status: safe mutation rules implemented; the known keyless category safety gap
is fixed by conservative deferral on the current feature branch. General
conflict-detection quality remains unproven.**

### Expected behavior

Compare a new claim with relevant existing knowledge. Distinguish a real
correction from an unresolved contradiction or facts that can coexist. Do not
silently accept incompatible PostgreSQL/SQLite claims as clear current truth.

### Already implemented

- Relation interpretation: same, correction, contradiction, unrelated or uncertain.
- Evidence-backed corrections create a new version and preserve history.
- Unresolved detected contradictions preserve both claims, mark them contested
  and add a contradicts relationship; uncertainty defers rather than overwrites.
- Scope/conditions/version checks and transactional mutation safeguards.
- Integration tests include PostgreSQL/SQLite contradictions using injected
  relation results. These prove engine behavior, not real-model detection accuracy.

### Remaining work

- [ ] Independently evaluate real-provider detection of corrections versus conflicts
  versus compatible facts, with recorded expected outcomes and agreed quality targets.
- [ ] Verify comparison coverage across different candidate classifications and
  missing/inconsistent claim keys. Current compatible-record selection requires
  matching type, scope and conditions; do not assume every semantic clash is compared.
- [ ] Cover different environments/times, ambiguous updates, negation, multiple
  conflicting records and paraphrases; fix missed conflicts or incorrect overwrites.
- [ ] Demonstrate the real integrated PostgreSQL-to-SQLite correction and unresolved
  contradiction cases through retrieval/viewer, with preserved evidence/history
  and visible contested state.

### Evidence inspected

- [Resolution policy](../src/contextbridge/engine/resolution.py): compatible-record
  filtering and NOOP/UPDATE/LINK_CONFLICT/CREATE/DEFER decisions.
- [Hosted interpreter](../src/contextbridge/formation/providers/interpretation.py):
  semantic comparison and explicit-correction evidence checks.
- [Write engine](../src/contextbridge/engine/write.py): transactional conflict
  relationships and contested flags.
- [Engine integration tests](../tests/integration/test_write_engine.py):
  preserved corrections, visible contradictions and competing-write safeguards.
- [Integrated report](v1-completion.md): connected implementation, offline flow
  evidence and pending general live-model quality approval.

Source/evidence inspection only; tests and live providers were not rerun.

## 6. State resolution

**Status: current/history mechanics implemented; automatic state interpretation
and full live semantic-history verification remain incomplete.**

### Expected behavior

An evidenced switch to SQLite makes SQLite applicable from its effective time,
while PostgreSQL remains inspectable as history and applicable to earlier queries.
Unresolved contradictions must not silently become a single authoritative state.

### Already implemented

- Version-checked transactional updates preserve previous versions, close their
  validity intervals, mark them SUPERSEDED and add supersedes relationships.
- Retrieval selects versions applicable at the requested as_of time, with scope
  and conditions; current and historical versions remain distinguishable.
- Tests explicitly cover PostgreSQL history versus current SQLite, interval
  boundaries, stale/competing updates and unsupported/out-of-order corrections.
- Explicit correction/history and actual Codex lifecycle have recorded passing evidence.

### Remaining work

- [ ] Prove automatic interpretation of an evidenced state transition through the
  current real-provider import path, including ambiguous and conflicting statements.
- [ ] Complete live correction/restoration indexing and historical semantic-search
  verification; these were unattempted in the recorded complete online attempt.
- [ ] Verify end-to-end temporal/conditional boundary cases and visible uncertainty
  against reviewed expected results, without treating newest arrival as truth.

Future-effective and out-of-order historical corrections are currently unsupported
or deferred. If required by the final agreed scope, implement and verify them;
otherwise record their explicit exclusion. They are not automatically required
by the simple current-versus-history example.

### Evidence inspected

- [Write engine](../src/contextbridge/engine/write.py): UPDATE branch preserves
  old validity/history and appends the new current version.
- [Memory API tests](../tests/test_memory_api.py):
  test_updates_preserve_history_and_retrieve_requested_time checks historical
  PostgreSQL and current SQLite at their effective times.
- [Retrieval repository](../src/contextbridge/persistence/repository.py):
  requested-time validity filters.
- [Completion report](v1-completion.md): explicit history/host proof and pending
  live historical semantic retrieval.

Source/evidence inspection only; no tests or live models rerun for this review.

## 7. Memory record

**Status: implemented for the reviewed requirement; no specific missing work identified.**

### Expected behavior and implementation

A structured durable knowledge unit such as FACT: Project uses SQLite.
Memory identity stores owner, scope/project, type, conditions and current version.
Linked versions store content, source/evidence, validity dates, status and optional
confidence, with a clear/contested decision state. Database constraints enforce
valid types, scope and version structure. The API supports creation and inspection.

### Evidence inspected

- [Persistence models](../src/contextbridge/models.py): Memory and MemoryVersion.
- [API schemas](../src/contextbridge/schemas.py): typed create/response and source fields.
- [API tests](../tests/test_memory_api.py): persistence across restarts/sessions,
  isolation, version history, replay and deletion.
- [Recorded verification](v1-completion.md): real database lifecycle and actual
  Codex write/inspect/correct/history/forget evidence.

No additional record-structure task is identified for this simple requirement.
This does not establish that extracted content is always correct; extraction,
normalization and admission quality remain tracked separately. Tests were not
rerun during this source/evidence review.

## 8. Graph edges

**Status: automatic reference-based related links implemented end to end on
`codex/pranit-related-memory-links`; broad retrieval-quality evaluation remains
with the teammate's benchmark workstream.**

### Already implemented

- Version-to-version edges with allowed types supersedes, contradicts,
  derived_from and related_to; no self-links or duplicate identical edges.
- Corrections create supersedes; detected conflicts create contradicts;
  validated derivations create derived_from. SQLite superseding PostgreSQL is covered.
- Inspection and bounded graph expansion use authorized edges, applying
  scope/time/condition eligibility. Forgetting removes attached edges.
- New writes automatically create related_to links for shared, exact code references
  present in both content and source evidence. Scope/conditions, current clear
  versions and bounded degree are checked transactionally. A scoped, paginated
  backfill command covers existing records. See [details](related-memory-links.md).

### Remaining work

- [x] Implement automatic related_to formation, inspection/retrieval use and
  forget/replay safety with real PostgreSQL integration tests. The chosen rule is
  explicitly evidenced shared code references; it does not infer arbitrary semantic
  relationships or assert that linked claims agree.
- [x] Compare direct search and graph expansion for eight explicit design cases
  using real PostgreSQL, including intended neighbors and distracting/ineligible
  controls. All match their design expectations; independent review remains pending.
- [ ] Independently review relevance labels/results before final quality acceptance.
- Hosted semantic relation proposals are tracked under #5. This related_to policy
  uses shared evidence-backed code references and makes no hosted requests; it
  does not claim arbitrary semantic-link accuracy.

### Evidence inspected

- [Edge model](../src/contextbridge/models.py): MemoryEdge constraints and version IDs.
- [Write engine](../src/contextbridge/engine/write.py): supersedes/contradicts creation.
- [Relationships](../src/contextbridge/persistence/relationships.py): derived_from.
- [Repository](../src/contextbridge/persistence/repository.py): scoped inspection/expansion.
- [Write integration tests](../tests/integration/test_write_engine.py) and
  [expansion tests](../tests/retrieval/test_expansion.py): history, conflict and traversal cases.
- [Link qualification](../src/contextbridge/engine/related.py),
  [automatic linker](../src/contextbridge/persistence/related.py),
  [integration tests](../tests/integration/test_related_links.py) and
  [implementation/check record](related-memory-links.md).

Automatic-link tests use real PostgreSQL and no hosted models; final validation
is recorded in the linked implementation document. Earlier review evidence above
remains historical and is superseded by this feature's implementation status.

## 9. Async consolidation

**Status: background infrastructure and derived-summary creation implemented;
live integrated quality, compaction and responsiveness not fully verified.**

### Already implemented

- Submission creates durable queued work; workers perform expensive proposal
  generation outside the request path and commit validated derived memories.
- Optional automatic scheduling: one batch per 15 minutes, up to 20 compatible
  current clear source memories; unchanged selections reuse job identity.
- Source provenance, scope/condition checks, retries/recovery, cancellation and
  forgetting safeguards. Original sources are preserved rather than deleted merely
  because a summary was created.

### Remaining work

- [ ] Complete the current integrated real-provider consolidation run and inspect
  the resulting summaries/provenance; it was unattempted in the full online attempt.
- [ ] Review merge/grouping quality: repeated database decisions should consolidate
  without losing rare facts, mixing conditions or presenting conflicts as agreement.
- [ ] Define and verify actual compaction behavior if "merge" requires fewer
  active redundant records; creating a derived summary alone does not prove cleanup.
- [ ] Measure foreground responsiveness while consolidation runs, including shared
  provider quota waits and concurrent work; asynchronous execution alone does not
  establish an acceptable latency under load.

### Evidence inspected

- [Queue/scheduler](../src/contextbridge/engine/consolidation_queue.py): durable
  submission, stable selections and bounded periodic scheduling.
- [Consolidation service](../src/contextbridge/engine/consolidation.py): worker-side
  generation, source validation and derived record creation.
- [Background tests](../tests/background/test_consolidation.py) and
  [queue integration tests](../tests/integration/test_consolidation_queue.py).
- [Integrated report](v1-completion.md): synthetic integration evidence and
  unattempted full-stack live consolidation.

Source/evidence inspection only; no new tests, measurements or provider calls.

## 10. Current agent query

**Status: implemented for the reviewed input requirement; no specific missing work identified.**

The agent supplies its present question as query text to memory_search or
memory_retrieve. Arguments validate a nonempty bounded query and optional scope,
conditions, as_of and limit. The gateway binds the project and sends the query to
the shared API, which invokes retrieval.

### Evidence inspected

- [Search arguments](../src/contextbridge/mcp_adapter/arguments.py): query validation.
- [Gateway](../src/contextbridge/mcp_adapter/gateway.py): retrieve forwards query
  and explicit filters to /v1/retrieval/search.
- [MCP tests](../tests/test_mcp_adapter.py): query calls, invalid arguments,
  project binding and richer retrieval endpoint.

No additional work identified for accepting and forwarding the current question.
Automatically invoking retrieval on every agent turn, interpreting "V1" as a
filter, and answer relevance belong to host integration/query understanding/
retrieval, not this input alone. Tests were not rerun for this review.

## 11. Query understanding

**Status: basic query handling and semantic matching exist; explicit intent/topic
interpretation is not implemented in the inspected retrieval path.**

### Already implemented

- Query validation, whitespace normalization and a fixed query time.
- Explicit caller filters and MCP project binding, rather than inferred authorization.
- Query embeddings for semantic matching, plus lexical/symbolic channels. This
  helps paraphrase matching but is not a structured intent/topic interpretation step.

### Remaining work

- [ ] Define and implement intent/topic interpretation for questions such as
  "What DB are we using for V1?", distinguishing database topic, current-state intent
  and any justified version/time constraint.
- [ ] Resolve query references against authorized project/session context;
  inferred project names must never expand access or override explicit filters.
- [ ] Define safe behavior for ambiguous terms (e.g. V1 as release label versus
  time), deferring or requesting clarification rather than inventing filters.
- [ ] Add query rewriting/expansion only where justified by the agreed design,
  with tests and evaluation showing improved relevance without changing intent.
- [ ] Evaluate against reviewed intent/topic/filter cases and the current search baseline.

### Evidence inspected

- [Retriever](../src/contextbridge/retrieval/retriever.py): normalize_query explicitly
  avoids inferring filters; search embeds the query and dispatches channels directly.
- [MCP gateway](../src/contextbridge/mcp_adapter/gateway.py): project binding comes
  from configured scope, not language understanding of the question.
- [Contract](team-plan/contracts-v1.md): inferred filters must not override explicit ones.

Source inspection only; no tests or model calls run in this review.

## 12. Hybrid retrieval

**Status: implemented and connected; broad measured quality acceptance incomplete.**

### Already implemented

- Semantic vector search with hosted embeddings/pgvector, lexical full-text
  matching and symbolic literal substring/claim-key matching.
- Owner/scope, conditions and effective-time eligibility before channel limits.
- Reciprocal rank fusion, version deduplication, bounded cards and liveness checks.
- Missing/stale embeddings and unavailable semantic service produce degradation
  warnings; lexical search remains available. Semantic similarity cutoff rejects weak matches.
- Real PostgreSQL/vector integration tests and limited live paraphrase/relevance evidence.

### Remaining work

- [ ] Complete a reviewed representative retrieval benchmark comparing keyword,
  semantic-only and hybrid results against agreed relevance targets.
- [ ] Evaluate fusion/channel bounds and similarity cutoff across paraphrases,
  identifiers, no-match queries and scoped/conditional/historical cases; tune on
  separate development cases and verify on held-out queries.
- [ ] Measure end-to-end retrieval latency, provider cost and larger-store behavior.
- [ ] Finish current full-stack live history/correction/restoration indexing checks;
  distinguish earlier embedding-only evidence from the later complete-runtime run.

### Evidence inspected

- [Repository](../src/contextbridge/persistence/repository.py): real semantic,
  lexical and symbolic channels, eligibility filters and similarity cutoff.
- [Fusion](../src/contextbridge/retrieval/fusion.py): ranked channel combination.
- [Repository tests](../tests/integration/test_repository.py): numerical vector
  search, identifiers, scope/time/conditions, stale embeddings and degradation.
- [Live embedding evidence](../evaluation/embeddings/README.md) and
  [Linux verification](linux-v1-verification.md): limited real-provider relevance results.

No tests/provider calls rerun; small successful examples do not prove general retrieval quality.

## 13. Graph expansion

**Status: bounded traversal and explicit labelled historical supersession context
implemented. Broader usefulness/quality acceptance remains pending.**

### Already implemented

- Optional traversal of stored edges, with deduplication, cycle/size bounds and
  per-record scope/condition/time/liveness checks; fills spare result slots only.
- Real repository expansion tests cover bounded traversal and isolation.
- Runtime enables expansion when configured or when formation is enabled.

### Remaining work

- [x] Define and implement an explicit historical-context path for "current DB,
  then follow supersedes to the former DB" if required for graph expansion.
  The new API/MCP context path labels old versions as historical and inapplicable
  at the query time. Standard current-result traversal remains validity-filtered.
- [ ] Make useful relationship selection/ranking measurable; current repository
  traversal follows eligible edges without relation-specific relevance ranking.
- [x] Verify traversal-depth semantics end to end. The teammate's merged fix gives
  one repository hop per retriever step; the new explicit history path is bounded
  separately to three directed supersession edges.
- [ ] Evaluate related-result relevance versus direct-search baseline, including
  filled result limits, no useful neighbor, stale/deleted nodes and historical context.

### Evidence inspected

- [Repository expansion](../src/contextbridge/persistence/repository.py): eligibility
  applies to both endpoints, bounded two-hop walk and bounded returned records.
- [Expansion policy](../src/contextbridge/retrieval/expansion.py): spare slots,
  applicability, deduplication and repeated repository calls.
- [Repository test](../tests/integration/test_repository.py):
  test_graph_expansion_filters_every_hop_and_bounds_depth.
- [Runtime](../src/contextbridge/runtime.py): activation configuration.

Source inspection only; no tests or provider calls run for this review.

## 14. Conflict-aware reranking

**Status: bounded conflict-aware ranking implemented; offline comparison recorded;
independent real-model usefulness acceptance pending.**

### Already implemented

- Scope, conditions and validity intervals exclude inapplicable versions before
  fusion. Correctly superseded PostgreSQL is excluded from a current SQLite query;
  historical queries may correctly return PostgreSQL.
- Remaining results rank by project scope, reciprocal rank fusion score, creation
  recency and version ID before the shared bounded conflict policy. The policy
  prefers clear cards in small relevance windows, groups disputed alternatives,
  retains uncertainty and warns when alternatives are missing or omitted.

### Remaining work

- [x] Define and implement bounded ranking using contested state and authorized
  contradiction relationships; verification never establishes a winning truth.
- [x] Preserve visible uncertainty and explicit alternative-omission warnings.
- [ ] Test highly similar stale records, clear versus contested results, historical
  queries and different applicable conditions; evaluate against current fusion.
- [ ] Verify that any policy improves useful valid context without allowing
  similarity, recency or confidence alone to determine truth.

The recorded synthetic comparison at the top covers technical behavior. Independent
relevance labels and real-provider quality remain pending.

### Evidence inspected

- [Fusion](../src/contextbridge/retrieval/fusion.py): is_applicable and order.
- [Retriever](../src/contextbridge/retrieval/retriever.py): verification follows
  selection and supplies labels without reordering/removing cards.
- [Retriever tests](../tests/retrieval/test_retriever.py): historical applicability
  and contested-state visibility.

Source inspection only; no tests or provider calls rerun for this review.

## 15. Selective verification

**Status: selective triggers and opt-in paired conflicting-evidence checks are
implemented. Real-model quality/cost approval and live retests remain pending.**

### Already implemented

- Selected contested, low-confidence or configured memory types trigger bounded
  verification (default maximum three per search); ordinary cards can skip checking.
- Authorized version/evidence inspection and exact record consistency checks.
- Clear eligible records can receive a hosted evidence judgment; errors remain
  uncertain with warnings rather than being presented as supported.
- Contested records immediately return uncertain before calling the evidence judge.
  This preserves disagreement but does not semantically examine competing evidence.

### Remaining work

- [x] Implement authorized examination of both claims' evidence without declaring
  a winner. `memory_context(verify_conflicts=true)` uses the new guarded path;
  original V1 card verification retains its conservative contested handling.
- [ ] Complete a successful current integrated live selective-verification run.
  The earlier run returned HTTP 400; later isolated supports-response connectivity
  succeeded but does not replace that full-path retest.
- [ ] Evaluate trigger coverage, support judgments and safe provider failure behavior
  on independently reviewed cases; record cost/latency versus verifying every card.

### Evidence inspected

- [Retriever](../src/contextbridge/retrieval/retriever.py): _needs_verification,
  bounded _verify and explicit uncertainty labels.
- [Verifier](../src/contextbridge/retrieval/verifier.py): contested short circuit,
  exact evidence/version checks and judge invocation for eligible clear records.
- [Integrated report](v1-completion.md) and [Linux check](linux-v1-verification.md):
  original HTTP 400 and later limited successful provider response.

Source/evidence inspection only; no new tests, provider calls or cost measurements.

## 16. Compact memory context

**Status: bounded structured cards implemented; consistent brevity/total token
budget and usefulness acceptance incomplete.**

### Already implemented

- MCP defaults to three cards and allows at most five; cards include content,
  scope, validity, source references and uncertainty/conflict labels.
- Full evidence/history are available through separate inspection.
- Legacy memory_search truncates card content at 1,500 characters with a flag.
- Rich memory_retrieve preserves full candidate content (bounded by the shared
  content schema) until stored-field validation. The shared context budget then
  enforces 12,000 total JSON bytes, 4,000 bytes per card and 1,500 content characters;
  long claims are replaced with whole-claim omission markers. These are not token bounds.

### Remaining work

- [x] Define and enforce overall context-size and per-card bounds for rich retrieval.
- [x] Preserve inspection references and uncertainty; mark whole-claim/card omissions
  instead of returning a prefix that can hide qualifications. Total-capacity and
  multibyte comparisons are recorded above. No tokenizer-specific limit is claimed.
- [ ] Evaluate whether selected cards are useful and sufficient, including long
  memories and no-match cases. Three cards alone do not guarantee low-noise context.

### Evidence inspected

- [MCP arguments](../src/contextbridge/mcp_adapter/arguments.py): default/max limits.
- [Gateway](../src/contextbridge/mcp_adapter/gateway.py): legacy card truncation
  and exact content preservation for richer retrieval.
- [Card schema](../src/contextbridge/contracts/messages.py): MemoryCard fields.
- [Retriever tests](../tests/retrieval/test_retriever.py): bounded/deduplicated cards.

Source inspection only; no tests or model calls rerun.

## 17. Manual UI and configuration / BYOK

**Status: local onboarding/BYOK and focused memory workspace implemented and tested;
independent usability, accessibility and platform acceptance remain pending.**

### Already implemented

- Streamlit controls for browse/search, explicit save/import, evidence/history,
  correction, consolidation submission/status, retirement/restoration and confirmed forget.
- Viewer connection settings: API address/token and selected project; explicit
  scope/condition/time controls and processing/indexing status.
- Backend BYOK configuration exists through local .env/settings and setup scripts
  for the selected Groq and Cloudflare stack. The new local settings panel edits
  that private installation file; the memory API/viewer client has no separate key store.
- UI tests and limited actual browser verification exist; complete independent
  usability/accessibility and Windows Docker walkthroughs remain pending.

### Remaining work

- [x] Define and build a local settings/onboarding interface for supported provider,
  model and BYOK setup, including safe replacement/removal of keys and clear
  configuration errors. Do not imply arbitrary providers are integrated.
- [x] Keep model credentials on the local service/operator side, masked and excluded from logs,
  responses and shared caches; distinguish provider keys from the API access token.
- [x] Provide configuration validation and an explicitly initiated bounded online
  connection check with visible cost/data implications.
- [x] Implement supported processing/project, grouping, raw retention, consolidation
  opt-in and daily token-ceiling controls. Automatic host capture still requires its
  separate opt-in; the fixed consolidation schedule remains explicit.
- [ ] Complete first-time-user setup, full memory lifecycle, error/recovery and
  accessibility walkthroughs on supported platforms.

### Evidence inspected

- [Viewer guide](inspection/README.md) and
  [app](../src/contextbridge/inspection/app.py): existing memory controls and API connection UI.
- [V1 setup](v1-guide.md) and [provider configuration](formation/provider-configuration.md):
  service-side .env/BYOK setup, rather than a viewer settings screen.
- [Linux verification](linux-v1-verification.md): limited actual browser checks.

The implementation and verification record at the top supersedes this section's
earlier review. Actual-user credentials/stores were not changed; no new live calls
were made. See [local workspace](local-workspace.md) for exact boundaries.

## Next components

Add each component's implemented behavior, remaining checklist and evidence here
after discussing and reviewing it.
