# Durable workers and consolidation (P4)

The optional worker stack uses Linux containers on Linux and Windows Docker Desktop.
PostgreSQL remains authoritative. Redis contains work UUIDs, with no conversation, candidate,
summary, embedding, or task result. Capture and reindex enqueue an outbox row in the same
transaction as their durable domain job. The scheduler backfills older accepted jobs in batches
of 100, maintains retention, and publishes due IDs. It never calls a model.

The base API/MCP installation needs neither Celery nor Streamlit. Install optional runtimes with:

```text
uv sync --frozen --extra workers --extra viewer --python 3.12
```

The viewer can then run with:

```text
uv run --extra viewer streamlit run src/contextbridge/inspection/app.py
```

## Configure approved providers

Set `CONTEXTBRIDGE_CAPTURE_PROJECT_ID` and a reviewed local factory in `.env`:

```text
CONTEXTBRIDGE_WORKER_FACTORY=your_package.worker:make
```

`make(settings, sessions)` returns `background.runtime.WorkerProviders`, containing an injected
`ModuleGateway` and optional embedder. The package must be installed in the worker image.
Use `engine.event_reader.EventReader(sessions, settings)` for formation admission's event lookup;
it enforces owner/project binding and raw retention. There is no fake production default.
Worker startup refuses an absent factory. An unavailable factory invocation records bounded safe
provider retries; it never exposes the import/provider exception.

Om's merged extractor/admission and Harshal's retriever/embedder/verifier work with the shared
store in recorded-backend integration tests. Actual models, production assembly, real consolidation
proposals, quality measurements, and host release checks remain pending. Do not configure
`tests.background.worker_factory:make` for real use: it is only a synthetic infrastructure probe.

After selecting and assembling approved providers, both OSes use:

```text
docker compose --profile workers up --build -d
docker compose --profile workers ps -a
docker compose --profile workers logs --tail 100 worker scheduler
docker compose --profile workers exec worker celery -A contextbridge.background.celery_app:app inspect ping --timeout=3
```

The default Compose launch omits workers. Redis has no host port and persists ID-only queue data
in `redis_data`. Keep `postgres_data` when recreating services. The worker image installs only
the locked workers extra; the API image keeps the lightweight base installation.

## Retry, timeout, and recovery

`work_items` is the ID-only outbox, execution lease, and diagnostic record. An owner lock and
fresh lease token serialize claims; every domain engine checks that token and its deadline before
committing. Obsolete, expired, or cancelled executions cannot write. Provider calls release DB
locks. A worker crash after a domain commit and before acknowledgment observes the committed
job on redelivery; saved candidate/proposal identities prevent duplicate mutations.

Defaults: three execution attempts; a 120-second work deadline; exponential retry backoff starting
at ten seconds and capped at 300; seven days of terminal diagnostic retention. Configure these
with `CONTEXTBRIDGE_WORKER_MAX_ATTEMPTS`, `CONTEXTBRIDGE_WORKER_TIMEOUT_SECONDS`,
`CONTEXTBRIDGE_WORKER_RETRY_SECONDS`, and `CONTEXTBRIDGE_WORKER_DIAGNOSTIC_RETENTION_SECONDS`.
Celery's soft process limit follows the commit deadline by one second; its hard process limit
follows by five seconds. The DB deadline still blocks late writes if an injected module catches
the timeout signal. Redis visibility timeout is the work timeout plus 30 seconds.

Only retryable failures retry. Exhaustion marks the domain job failed with a safe code. Broker
publication failure does not spend a provider attempt; the durable outbox remains for recovery.
Publication followed by a crash before its DB marker may publish twice safely. A scheduler restart
or Redis queue loss recovers pending/expired work from PostgreSQL; delivery may take up to the
configured work timeout plus 30 seconds. Celery results and task event payloads are disabled.
Structured engine logs contain IDs, status/reason codes, and durations, never source text.

`GET /v1/jobs/{job_id}` retains the existing capture response. The separate authenticated
`GET /v1/worker/jobs/{work_id}` returns work/job IDs, kind, status, attempts, safe reason, duration,
and update time. It obeys configured developer/project binding. It may return 404 after diagnostic
retention; domain status/cancellation identities remain. No transcript export is added.

## Consolidation

Use `ConsolidationService(session, settings).enqueue(query, version_ids, request_id)` for an
explicit, bounded selection of 1–200 distinct current versions. Mixed developer/project scope,
historical selections, differing conditions, contested sources, and stale versions are rejected.
The query text is not stored. The job stores source IDs/context hashes and a fixed expiry.
The worker calls the injected `Consolidator.propose(records)` outside DB locks, validates at most
20 V1 proposals, saves their interpretation once, then rechecks all live sources and evidence refs.
The final summaries and `derived_from` edges commit atomically.

V1 proposals have no memory type; derived snapshots use `STATE`. Original facts, including rare
ones, remain intact. The summary's primary Source is the first referenced source; every source's
original evidence remains reachable through its derivation edge. This establishes traceability,
not semantic support. Proposal IDs are replay identities per owner; changed reuse conflicts.
Successful jobs erase the saved proposal content, and failed/deferred proposal retention is bounded
by the candidate-retention setting. Real Om consolidation policy remains pending.

## Forgetting

Forget holds the shared owner lock, removes the bounded transitive derived-memory closure, and
clears capture/candidate/plan copies, versions, evidence, edges, vectors, consolidation selections,
saved proposals, and related request/context fingerprints. It cancels associated work and clears
execution tokens. In-flight extraction/indexing/consolidation and redelivered IDs cannot recreate
that content. Cancellation markers contain safe identity/status metadata only.

Before interpretation there is no trustworthy fact-to-buffer mapping. Consequently, forgetting
also erases all buffered capture work in the same owner/scope/project, including other pending
events in that scope. Their ingestion replay returns `CANCELLED`; preserved unrelated memories
remain readable. Other owners/projects remain untouched. A future intentional fresh import is a
new input, not a retry. No server memory-content cache is introduced; Redis stores IDs only, and
the merged viewer uses no Streamlit cache. External client copies and backups/WAL retain their
separate retention limitations.

## Validation

The full test suite with `--all-extras` covers real merged modules using recorded backends,
source/condition boundaries, saved interpretations, rollback, concurrent claims, expired leases,
forgetting during all three processing paths, and schema preservation/recovery. Linux CI supplies
an isolated Redis test DB 15 for real Celery prefork probes. Native Windows explicitly skips the
three prefork probes and numerical vector checks; Windows Docker Desktop remains an actual host
verification gate.

For a newly created disposable full Compose stack:

```text
uv run --all-extras python scripts/worker_stack_probe.py
```

The probe refuses existing resources named `contextbridge-worker-probe`, uses a dedicated
`contextbridge_worker_probe_test` database, ports 55436/18036, synthetic test-only providers and
credentials, then checks ingestion → worker commit → correction → whole-stack restart → preserved
history → forget → restart → cancelled redelivery. It removes only its own test containers/volumes.
It requires Compose supporting the ports `!override` tag and never tests a development database.

Runtime references: [Celery tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html) and
[Redis transport](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html).

Local evidence: 697 tests passed on each pgvector PostgreSQL 17/18 database, without skips;
17 existing Alembic deprecation warnings remain. Ruff/format, frozen lock, schema drift and full
migration round trips passed. The full disposable Compose restart/forget probe passed on Linux.
Actual Windows Docker Desktop and live model quality checks remain pending.
