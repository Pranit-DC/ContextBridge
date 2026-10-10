# Pranit — shared engine, storage, integration, and reliability

Your outcome: Om's candidates become safe persistent memory, Harshal's retrieval uses the real
store, and actual agents can use the complete system on Linux and Windows.
You own the connecting layer. You are not expected to implement Om's extraction or Harshal's UI.

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
