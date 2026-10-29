# Remaining tasks Phase 4 — current integrated provider paths

Base: `425b6449916382a39548c30a1b37ba325516f43e` (`origin/develop`, fetched 29 October 2026).
No unmerged phase branch is required. Synthetic responses exercise current hosted adapters and
the shared PostgreSQL engines. They establish protocol/policy behavior, not general model quality.
Shared integration/tests/docs are Pranit's ownership; formation/retrieval modules retain their owners.

## Execution boundary

The existing `.contextbridge/reliability-online-20261014/request-ledger.sqlite` was inspected
read-only: **Groq 1, Cloudflare 0, stopped=true**, HTTP 200 followed by invalid provider output.
It is a later ledger than the public 5/6 request attempt. No stopped ledger was reset, replaced
or resumed. **All Phase 4 live checks are unattempted; additional live requests: 0/0.**
No credentials or `.env` were changed. Ordinary tests use synthetic keys, MockTransport and
test-only ledgers. Original request ceilings (40 Groq / 20 Cloudflare), token budgets and paid
provider restrictions remain unchanged. Virtual clocks skip offline waiting only; durable numeric
PostgreSQL quota reservations and SQLite request counting still run.

## 1. Extraction

Added a hosted-assembly HTTP replay covering six atomic reusable claims: production applicability,
negation, a rare repair identifier/flag, preference, state and an explicit dated occurrence.
The occurrence's raw FACT/event-time output is retained separately in the test from its local
EVENT/source-time corrections and final candidates. Scope/uncertainty checks prevent uncertain
claims becoming stored truth. The shared write engine persists the final synthetic candidates.
The extraction HTTP replay makes 2 mocked Groq calls; no external requests or quality scores.
[Saved synthetic stages](phase4-evidence/extraction-stages.json) retain raw provider claims,
the separate local correction counts and final candidates. These are injected responses.

Checks and later task results are recorded below as each task completes.

## 2. Admission

The current hosted assembly passed five synthetic HTTP/engine cases: filler rejected,
preference and rare lesson admitted, unsupported assertion rejected, ambiguity deferred.
Each case made 2 mocked Groq requests and no live calls. Extraction tests: 3 passed;
admission/sensitivity tests: 6 passed.

`uv run python -m scripts.phase4_admission` replays all 29 existing O2 design-labelled cases
at nine confidence/usefulness settings. Default 0.8/0.6 matches all 29 existing labels;
changed outcomes and counts are in [the safe artifact](phase4-evidence/admission-sensitivity.json).
Labels remain **design_labels_pending_team_review**. This is sensitivity, not calibration,
independent review, or an approved accuracy target. Production thresholds were not changed.

## 3. Duplicate rejection

Fresh synthetic events reproduced a defect before the fix: the same primary-database property
paraphrased under FACT rather than DECISION created a second clear memory (1 failed / 4 passed).
The hosted interpreter excludes cross-category comparisons, so its unrelated result reached CREATE.
The shared runtime's hosted relation boundary now defers category disagreement for the same non-null claim key,
without guessing equivalence, rewriting metadata, or changing V1 contracts. This is a conservative
core safeguard within Pranit's ownership, not a claim of general semantic duplicate detection.

The first policy-wide guard passed 27 focused tests but failed 15 existing comparison checks in
the full suite: it skipped capable injected interpreters and blocked unrelated classifications.
The final guard is limited to built-in hosted assembly. Existing generic comparison behavior is
preserved, and a sixth new case confirms unrelated Python runtime facts can still be admitted.
The corrected focused comparison/runtime/duplicate/transition/budget run: **57 passed, 1 xfailed**.
Exact repeat and positive paraphrase reject without another version; unsupported condition drift
defers; separately evidenced production applicability stays separate. Durable job replay makes no
new HTTP call. Each case uses at most 5 mocked Groq calls; live duplicate resolution is unattempted.

## 4. Conflicts and state transitions

**6 passed, 1 strict expected failure.** Real hosted adapters with scripted HTTP proposals and
PostgreSQL demonstrated correction history/closed intervals/supersedes edges, unresolved contradictions
with two contested records and a contradicts edge, historical versus current retrieval, separate
development applicability, refusal of negated/backdated correction and atomic deferral for multiple
conflicts. Tests inspect version IDs, stored edges and uncertain contested retrieval cards.
Each case uses at most 9 mocked Groq calls; live state interpretation remains unattempted.

**Unresolved owner defect (Om):** `formation/providers/interpretation.py:ChatRelationInterpreter.compare`
returns unrelated immediately when types differ. An explicit keyless DECISION `Use PostgreSQL database.`
followed by an audited FACT paraphrase `SQLite is our database.` with null claim_key creates a second
clear record without a relation request. Task 3's same-key hosted boundary cannot identify this
keyless relationship. `test_keyless_cross_category_paraphrased_conflict_must_not_become_clear_truth`
is a strict xfail that exposes the safety failure. Om must allow semantic cross-category comparison
(or return uncertainty); shared resolution already defers non-unrelated cross-category proposals.
No Om source file was changed, and this defect is not described as resolved.

## 5. Indexing and history

**1 new integrated test passed** on pgvector PostgreSQL 18. Current-version discovery queued each
initial/corrected/restored version once. Actual Cloudflare HTTP parsing, finite 1024-dimensional
vectors, durable indexing and PostgreSQL semantic distance ran with injected vectors. Inspection
preserved three versions and original evidence. Both the direct semantic channel and assembled
retriever selected the old version before correction, version 2 before retirement, nothing in the
inactive retirement gap and restored version 3 currently. Historical vectors remain stored.
The replay made **7 mocked Cloudflare requests** (3 document, 4 query); no live requests. This
verifies temporal/index plumbing, not real embedding relevance. No indexing/history defect found.

## 6. Consolidation

**4 integrated cases passed.** Current hosted grouping and evidence-verification adapters feed the
actual Consolidator and shared ConsolidationService. Rare E731/repair_index.py/--dry-run content
survives completely; derived_from edges point from the summary version to both original versions;
source inspection returns original evidence and source references. Originals remain active and
unchanged. Job replay adds no requests. Forgetting one source removes the derived summary and edges
while retaining the other original. Different conditions reject before provider calls; unsupported
disagreement and uncertain groups produce no summary. Compatible/unsupported/uncertain cases each
make 2 mocked Groq calls; incompatible conditions make 0. No live consolidation attempted.
No active-record compaction or general related_to formation was added. No product defect found;
one initial harness assertion expected the wrong internal exception type and was corrected.

## 7. Selective verification

**6 new checks plus 5 existing budget tests passed (11 total).** Current hosted search-evidence
adapter and assembled retriever preserve supported / uncertain labels for supports, contradicts
and insufficient judgements. A synthetic HTTP 400 on the earlier failure path, timeout and malformed
judgement keep the card uncertain with VERIFICATION_UNAVAILABLE; raw provider diagnostics are not
returned. HTTP 400/timeout stop the temporary ledger and prevent a Cloudflare call. Each case makes
1 mocked Groq request. A malformed HTTP-200 judgement is rejected locally; transport accounting
records its HTTP success, while the caller reports verification unavailable.

The earlier real HTTP 400 cause remains unestablished because its body was not retained. This
synthetic regression proves safe current behavior, not that the real provider now accepts the
request. The stopped existing live ledger remains unchanged; the real retest is unattempted.

## Bounded ledger regression found by the full suite

The first full run also reproduced Windows `msvcrt.locking` EDEADLK while multiple threads
initialized/used the same ledger. The ledger now serializes same-process threads by normalized
absolute path before taking the existing OS lock. Independent processes still use the OS lock;
SQLite reservations, request ceilings, transport stop behavior and all stopped ledger data remain
unchanged. Weakly held per-path locks avoid retaining every prior test path. A new eight-thread
regression reserves 32 requests exactly and confirms a separately opened stopped ledger cannot
reserve a Cloudflare request. All 6 bounded-ledger tests pass; the wider corrected run above passes.
No live ledger was opened for writing as part of this fix.

## Final validation and reproduction

All database execution used the newly created **contextbridge_phase4_test** on PostgreSQL 18.6
with pgvector 0.8.7. No real memory store, `.env`, provider credentials or unrelated work was changed.
Source changes stay in shared runtime assembly and the existing bounded demo ledger; Om/Harshal
modules, common contracts, schema, scope/version checks and deletion fences are unchanged.

| Check | Final result |
| --- | --- |
| `uv run ruff check .` | Passed; initial unrelated nested-worktree error no longer present; that worktree was not edited here |
| `uv run ruff format --check .` | Passed |
| `uv run alembic upgrade head` | Passed on the dedicated test database |
| `uv run alembic check` | Passed; no new upgrade operations |
| `uv run --all-extras pytest --cov=contextbridge --cov-report=term-missing --tb=short` | **1492 passed, 0 failed, 4 skipped, 1 xfailed**, 17 existing Alembic warnings; 214.65 s; 87% parent-process coverage |
| `uv run pytest tests/integration -k phase4 -q --tb=short` | **32 passed, 0 failed, 1 xfailed**, 233 deselected; 31.03 s |
| Existing-label threshold sensitivity | 29 cases, 9 settings; no labels/targets/production thresholds changed |
| Configured-credential exact-value scan | Passed; zero matching proposed files |

The four skips are Linux prefork/Redis transport probes at `tests/background/test_worker_transport.py`
lines 147, 167, 203 and 227. They were not exercised on Windows. The one strict xfail is the
keyless cross-category safety defect described in task 4; it remains a release limitation.
The initial full run had **16 failed, 1474 passed, 4 skipped, 1 xfailed**, 17 warnings, 275.15 s:
15 failures exposed the overbroad first guard and one exposed the Windows ledger defect. Both
in-scope fixes were corrected and the entire suite was rerun. Initial extraction/date-format and
consolidation exception assertions were harness errors, corrected before their task commits.

[Machine-readable checks](phase4-evidence/checks.json),
[live preflight](phase4-evidence/live-preflight.json) and
[per-case mocked usage](phase4-evidence/mocked-provider-usage.json) contain only synthetic/content-free
evidence. The final focused run counted **87 mocked Groq / 7 mocked Cloudflare requests across 32
independent test ledgers**. These are not live usage or a resumed online budget. Limits remain
40/20 for each bounded ledger, with unchanged runtime token limits and strict output ceilings.
All hosted-replay requests assert the selected model and at most 1024 output tokens.

**Additional live usage: 0 Groq / 0 Cloudflare requests.** The existing stopped ledger remains
1/0 and stopped. Actual model tokens, billing, quality and live acceptance of the earlier HTTP 400
request were not measured. All seven live areas, independent quality review/calibration and Linux
worker probes remain unattempted here; no general model-quality approval is inferred.

To reproduce, configure only a dedicated `_test` database using README test instructions, then run:

```text
uv run alembic upgrade head
uv run alembic check
uv run pytest tests/integration -k phase4 -q --tb=short
uv run python -m scripts.phase4_admission
uv run --all-extras pytest --cov=contextbridge --cov-report=term-missing --tb=short
```

Tests inject synthetic credentials and HTTP responses. No live execution switch is provided by
the new harness. Do not use a fresh ledger to bypass the existing online stop.
