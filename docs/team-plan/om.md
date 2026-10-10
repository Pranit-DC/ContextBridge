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
```
