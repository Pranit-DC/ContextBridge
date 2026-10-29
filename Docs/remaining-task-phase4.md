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
The shared resolution policy now defers a category disagreement for the same non-null claim key,
without guessing equivalence, rewriting metadata, or changing V1 contracts. This is a conservative
core safeguard within Pranit's ownership, not a claim of general semantic duplicate detection.

After the fix, all five new cases and existing resolution/formation checks passed: **27 passed**.
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
clear record without a relation request. The Phase 3 same-key engine safeguard cannot identify this
keyless relationship. `test_keyless_cross_category_paraphrased_conflict_must_not_become_clear_truth`
is a strict xfail that exposes the safety failure. Om must allow semantic cross-category comparison
(or return uncertainty); shared resolution already defers non-unrelated cross-category proposals.
No Om source file was changed, and this defect is not described as resolved.
