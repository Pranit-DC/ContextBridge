# Pranit — shared engine, storage, integration, and reliability

Your outcome: Om's candidates become safe persistent memory, Harshal's retrieval uses the real
store, and actual agents can use the complete system on Linux and Windows.
You own the connecting layer. You are not expected to implement Om's extraction or Harshal's UI.

## Implementation status — 11 October 2026

P1 is implemented on `feat/pranit-ingestion-contract` with
[PR #10](https://github.com/Pranit-DC/ContextBridge/pull/10) merged into `develop`.
Its required GitHub checks passed, including native Linux/Windows jobs.
It includes shared contract V1 models/protocols, authenticated project-bound manual ingestion,
durable event/job replay, bounded raw retention and expiry, and injected test-only module substitutes.
Setup and limitations are in [durable ingestion](../ingestion.md).

Local validation: Ruff lint/format passed; PostgreSQL 18 migrations, drift checks, full migration
round trip, and 173 tests passed (97% coverage; no skipped tests). Migration tests also preserve
existing explicit memory, history, and replay semantics. Actual Windows/agent host checks remain
separate verification. No new model/provider dependencies were added.

P2 is implemented separately on `feat/pranit-write-engine`, rebased onto merged P1 in
[PR #11](https://github.com/Pranit-DC/ContextBridge/pull/11) to `develop`.
P2 is merged into `develop`; Linux/Windows CI passed. It saves extraction/admission/plans once, executes scoped version-checked
writes, preserves conditional/contested claims and relationships, cancels capture copies on
forget, removes scoped derivation closures, and supplies the agreed paginated browse API/fixtures.
See [write engine](../write-engine.md) for invocation and exact limits. The synchronous engine
uses explicitly injected providers; accepted events do not automatically start processing.

P2 local validation: Ruff lint/format and `uv lock --check` passed; PostgreSQL 18 full migration
round trip and drift checks passed; 212 tests passed with 95% coverage and no skipped tests.
Regression tests cover competing corrections, rollback/retry, expiry/forget during processing,
legacy duplicates, scoped derivation cleanup, and owner/filter-bound pagination. Nine warnings
come from the existing Alembic `path_separator` deprecation. Real provider/host tests remain
pending; test substitutes establish store behavior rather than model quality.

P3 is implemented on `feat/pranit-retrieval-persistence`, rebased onto `develop` after P2 and
the teammate formation/retrieval/viewer PRs merged.
It supplies the agreed PostgreSQL lexical/symbolic/semantic repository, scoped two-hop graph,
authorized inspection/liveness, version/model-linked embeddings, bounded durable reindex batches,
vector/reindex deletion fences, and the injected V1 retrieval API. The pinned pgvector image
preserves the PostgreSQL 18 volume; native core-only installs report semantic unavailability.
No Om/Harshal module or V1 message shape changed; no provider SDK dependency was added.
See [retrieval persistence](../retrieval-persistence.md) for integration and backup/upgrade steps.

P3 local validation: full suites on pgvector PostgreSQL 17 and 18 each passed 246 tests with
95% coverage and no skips. Lint/format, lock, schema drift, and migration preservation passed.
A disposable same-volume image upgrade, core-only migration/fallback, and logical backup/restore
preserved explicit memory/history. CI definitions cover vector 17/18 and native Windows core;
P3 [PR #18](https://github.com/Pranit-DC/ContextBridge/pull/18) merged into `develop`; its
Linux/Windows CI passed. Actual Windows Docker Desktop/real model checks remain pending. Existing
Alembic deprecation warnings remain. The rebased full suite passed 654 tests; the optional Streamlit screen module was explicitly
skipped because the viewer dependency is not installed. P4 is implemented separately on `codex/pranit-workers-consolidation`, updated from `develop`
after P3 merged. It adds optional Celery/Redis services, transactional ID-only outbox, bounded attempts,
deadline/token fences, recovery, safe diagnostics/retention, source-checked consolidation commit,
and complete engine-managed forgetting. Actual merged formation/retrieval modules are covered with
recorded backends; real model quality/production assembly remains pending. Harshal's requested
optional Streamlit dependency and IPv4 setup fix are supplied in shared files; no teammate-owned
module or test was edited. See [worker handoff](../workers.md).

P4 validation: both pgvector PostgreSQL 17/18 full suites passed 697 tests, with no skips and
89% reported coverage (subprocess/AppTest executions are not collected by the parent coverage
run). Ruff/format, lock, migration preservation, schema drift, and full migration round trips passed.
Real Redis/Celery probes cover kill after commit/before acknowledgment, bounded timeout retries
through the actual formation wrapper, broker outage/recovery, and decoded ID-only messages.
All 15 viewer screen tests run with the optional dependency; shared fixtures isolate inherited CI
credentials. The disposable full Compose stack also passed durable ingestion, correction, whole-stack restart
with preserved history, forgetting, another restart, and cancelled redelivery. Its synthetic test
image uses a whitelisted temporary build context; the production image has no fake provider.

P4 is ready for a focused draft PR to `develop`; required local checks passed. Remote P4 CI
and team review remain separate checks. P5 is
next: actual provider assembly/import adapters and release gates. Real consolidation policy,
model/host quality checks, and actual Windows Docker Desktop checks remain pending.

Read [common contracts](contracts-v1.md) and [team workflow](README.md). The contracts are planned
interfaces; the existing explicit API and MCP tools must keep working throughout development.

## Your files and boundaries

You own existing core Python/API/config/model/security files, existing `mcp_adapter/`,
new `contracts/`, `engine/`, `persistence/`, `background/`, `capture_adapters/` under
`src/contextbridge/`, all migrations, shared dependencies/lockfile/Compose/CI, existing root
tests and shared fixtures, new `tests/engine/`, `tests/background/`, `tests/integration/`,
setup/demo scripts, and common documentation.

Do not edit `formation/`, `retrieval/`, or `inspection/` or their tests. Give the owner a failing
case or requested interface adjustment. One owner for shared files prevents competing migrations
and lockfile edits. Keep shared work in small PRs, so this responsibility does not delay everyone.

## Start now without waiting

Create `feat/pranit-ingestion-contract` from latest `develop` using the [branch steps](README.md).
Start with today's dependencies. Build contract types, a fake extractor returning
[candidate.json](fixtures/candidate.json), and a fake retriever returning
[retrieval-result.json](fixtures/retrieval-result.json). These let you test your wiring while
Om and Harshal build their real implementations. Your first PR needs no model account.

## P1 — shared types and durable interaction ingestion

Deliver:

- Shared validation types matching contract version 1, without changing existing public schemas.
- Authenticated, project-bound interaction ingestion; durable event/job records and migrations.
  Define and document the new interaction and job-status endpoints before exposing them.
- Stable event replay, safe rejection, bounded buffer, timestamps, and retention configuration.
- Configurable injected module entry points; fake modules for engine tests, not production defaults.

Acceptance: replaying one event produces one ingestion record; changed payload with the same ID
conflicts; another project/owner cannot access it; credentials/oversize/invalid timestamps are
rejected safely; a restart does not lose accepted work. Test schema upgrade and drift.

## P2 — safe write engine and relationship storage

Deliver:

- Candidate/evidence validation and claim metadata. Execute admission decisions and WritePlans.
- New claim, exact duplicate, explicit correction, conditional coexistence, contested group,
  and deferred uncertainty behavior. Preserve existing explicit create/update semantics.
- Version-to-version conflict/derivation relationships with a small graph in PostgreSQL;
  a separate graph database is unnecessary for this V1.
- Transactional version checks and stable candidate/job identities. Store extraction results
  once so a retry cannot produce a different interpretation without an explicit reprocessing flow.
- Safe, scoped browse and status APIs needed by Harshal; publish paginated response contracts
  in a small PR and provide fake responses without making his viewer wait for the DB implementation.

Acceptance: two competing corrections cannot both win; identical retried candidates do not add
versions; different environments do not overwrite each other; unsupported/backdated corrections
defer; unproven contradictory claims stay visible as contested. Test every read/write boundary.

## P3 — retrieval persistence and infrastructure

Deliver:

- Harshal's repository interface: filtered lexical/semantic/symbolic search, bounded scoped graph
  expansion, authorized inspection, and a current-validity/deletion check before returning cards.
- pgvector-enabled database image and reviewed Alembic migration. Keep current volumes/data;
  document backup/restore and extension availability. Do not destroy volumes to fix startup.
- Version-linked vectors plus embedding model/dimension metadata, reindex jobs, and stale-index
  handling. Never rank incompatible vectors together or expose a stale deleted version.
- Shared optional dependencies/config requested by Om and Harshal; keep the base API usable
  when an optional viewer/model provider is not installed or configured.

Acceptance: real PostgreSQL channel tests apply scope/time/conditions before limits; historical
queries return the right version; missing embeddings report degradation; incompatible model
dimensions are rejected; upgrading the existing foundation preserves stored memory/history.

Native Windows CI currently uses PostgreSQL 17 without an assumed vector extension. Add an
explicit supported extension setup or a separate real vector-container integration job, while
keeping native client tests. Never silently skip vector integration and call Windows fully tested.
Record Docker Desktop testing of the full stack on a Windows teammate's machine.

## P4 — workers, consolidation commit, and complete forgetting

Deliver:

- Celery/Redis worker services in Linux containers on both OSes, with PostgreSQL durable job
  records/outbox. Broker messages contain IDs. Add bounded retries, timeout, status, and recovery.
- Execute Om's consolidation proposals after rechecking live sources, scope, conditions, and
  evidence. Store derivation/provenance so derived content can be invalidated later.
- Forget across raw buffers, candidates, versions, edges, vectors, derived summaries, caches,
  and pending jobs. Commit-time cancellation/deletion fences stop in-flight work resurrecting it.
- Safe structured logs: IDs, durations, status/reason codes, not source content or secrets.
  Support job diagnostics and bounded retention without leaking private conversations.

Acceptance: kill/restart a worker after DB commit but before acknowledgment; observe one mutation.
Simulate broker outage and recover outbox work. Exhausted provider retries show a safe failure.
Forget during extraction, indexing, and consolidation; pending/redelivered jobs cannot recreate
content. Restart all containers and verify persistence, readiness, and recovery.

## P5 — real adapters, end-to-end wiring, and release checks

Deliver:

- Wire Om's and Harshal's merged entry points to the real engine. Add integrated tests that use
  the actual modules and DB; retain fake tests separately for isolated failures.
- Bind import/capture adapters to the common ingestion API. Start with documented transcript
  import; automate a host only after verifying its available hooks and event format.
- Keep the MCP interface agent-neutral. Test Codex and Claude Code on the same machine and
  across machines; verify one client's correction is visible in another fresh session.
  Additional hosts, including Gemini, need a documented actual compatibility test before support claims.
- Packaging/setup, optional provider configuration, health checks, retention, recovery, and
  supported-feature matrix; a clean-machine runbook with ordinary error recovery.

Acceptance: real capture/import → extraction → admission → persistent version → hybrid search →
viewer evidence → explicit correction → cross-agent read → forget. Pass [all release gates](README.md#required-release-gates),
including Linux/Windows CI, actual host tests, model-quality report, and team review.
Opening a release PR is separate from merging it: the team owns `main` and release approval.

## Tests and review evidence

Run focused tests as their directories are introduced:

```text
uv run pytest tests/engine tests/background tests/integration
uv run ruff check .
uv run ruff format --check .
```

Use the README's dedicated `_test` DB instructions for full tests, Alembic upgrade/check, and
disposable migration round trips. Add tests for the actual failures listed in each phase;
do not merely assert that a fake returned its predefined answer. Record real provider and agent
checks separately, without copying credentials or private chats into evidence.

Each PR must name its contract version, schema changes, demonstrated outcome, tests, and remaining
integration. Once a PR merges, start the next from updated `develop`.

## Dependencies and independent fallback work

If Om's provider is pending, use the fake extractor and work on transactional resolution,
retention, workers, or adapters. If Harshal's real retriever is pending, use the fake retriever
and complete filtered repository queries, vector persistence, or deletion tests.
Fakes let you finish infrastructure; final real integration remains pending until connected.

## Prompt for your coding agent

```text
Work on Pranit's next unfinished phase in docs/team-plan/pranit.md, not the whole backlog at once.
Read AGENTS.md, README.md, docs/architecture.md, and docs/team-plan/contracts-v1.md first.
Create a focused feature branch from develop; every PR targets develop; never modify main.
Change only Pranit-owned files listed in the team plan. Do not implement or edit Om/Harshal modules.
Use injected test substitutes for unavailable modules, and label real integration as pending.
Preserve existing API/MCP compatibility, scope boundaries, evidence, versions, and forgetting.
Add migrations for schema changes and meaningful failure/concurrency tests.
Run all required checks on a dedicated test DB. Report delivered behavior and limitations accurately.
Ask before changing the agreed shared contract; do not guess missing project decisions.
```
