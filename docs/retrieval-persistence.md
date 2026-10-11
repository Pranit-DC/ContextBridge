# PostgreSQL retrieval and reindex infrastructure (contract V1, P3)

`PostgresRepository` implements the agreed dictionary interface in
`contextbridge.contracts.interfaces`: `search_channel`, `expand`, `inspect`, and `is_live`.
It uses the existing store and the server's developer identity. Harshal's ranking, embedder,
verification policy, and UI stay in his modules; there is no production substitute for them.

## Channels and read boundaries

Every channel applies owner, explicit scope/project, all stored conditions, and effective
`[valid_from, valid_to)` before ranking and limits. Developer-global records require an explicit
developer query or `include_developer`. One repository instance fixes a null `as_of` once;
the HTTP service supplies the same explicit instant to every module call and final check.
Historical queries can return an applicable SUPERSEDED version.

- Lexical: PostgreSQL English full-text matching and rank, with UUID tie-breaking.
- Symbolic: escaped literal substring matching in content or claim label; underscores and
  punctuation retain their meaning. It does not infer identifiers or query filters.
- Semantic: pgvector exact cosine distance over compatible, authorized version embeddings.
  Model ID, dimensions, and content fingerprint are checked before ranking/limits. No ANN index
  or approximate post-filtering is used. Missing extension/model/vectors or stale coverage returns
  available matches and records `EMBEDDING_UNAVAILABLE`; HTTP combines this with degraded output.

Channel limits are 1–200, separately from the 1–20 HTTP card limit. Graph expansion excludes
seeds, allows two hops, visits at most 200 versions, and filters both endpoints at every hop.
Foreign/ineligible seeds fail safely. Inspection selects the applicable version, includes history
up to the resolved time (at most 200; larger histories fail safely), and only eligible edges.
`is_live` repeats the authorized effective-time query; deleted versions never qualify.

## Embedding storage

`embedding_models` fixes dimensions for each owner/model ID. Use a new model ID for a changed
model/version/dimension definition. `memory_embeddings` uses a version/model key, declared
dimensions, content SHA-256, and index time. Version deletion cascades to embeddings.

Vectors use PostgreSQL one-dimensional `real[]` float32 storage and are cast to pgvector for
exact distance queries. This portable schema keeps native core-only PostgreSQL usable without
installing a model SDK or extension. The vector-backed deployments execute real pgvector SQL;
this is not a Python similarity fallback. Database constraints enforce dimensions and reject
null/nonfinite/zero vectors. Providers are also validated for finite, nonzero float32 values,
batch length, model ID, and dimensions before persistence. No new Python dependency is required.

The reviewed migration `70693e8576e5` adds these tables and durable reindex tables. It enables
`vector` if the extension is available on the server. If the migration already ran on core-only
PostgreSQL, install pgvector and have the database administrator run `CREATE EXTENSION vector`
in that database afterward. Application startup never installs extensions or creates schemas.
Downgrade removes application index tables and preserves an existing/shared extension.

## Durable reindex batches

`IndexService(session, developer_id).enqueue(query, version_ids, model_id, dimensions, request_id)`
accepts 1–200 distinct authorized version IDs in one explicit scope. Conditions/time are checked
at selection, and target IDs plus source/context hashes are persisted. Reuse the same request ID
and selection on retry. Mixed project/global indexing uses separate jobs.

Call `IndexService(...).process(job_id, approved_embedder)` to execute a batch. It reads bounded
content from the real versions and releases write locks before the provider call. Before committing,
it reacquires the owner lock, rechecks job/targets/source context, and saves vectors and success in
one transaction. Redelivery after commit returns success without another provider call. Competing
deliveries use the first committed batch. Transient provider failures are retryable deferred jobs;
malformed output is a safe failure. Queue publication, automatic retries/backoff, timeout enforcement,
maintenance, and operational status endpoints remain P4 work. `inspect(job_id)` is scoped library
diagnostics with IDs/model/status/reasons only; reindex jobs contain no saved source text.

Forget cancels associated reindex jobs, clears their request fingerprint/targets, and deletes linked
vectors in the memory-deletion transaction. In-flight/redelivered work cannot recreate deleted
versions. Updating a source never attaches its old embedding to a new version: an older index can
serve a valid historical query, while the new current version reports missing coverage until indexed.
External copies/backups and future cache/outbox/consolidation cleanup remain separate lifecycle work.

## HTTP wiring

Authenticated `POST /v1/retrieval/search` takes RetrievalQuery and returns RetrievalResult from
the unchanged V1 contract. Inject `ModuleGateway(retriever=...)`, `embedder`, and `verifier` through
`create_app`; the default service returns safe 503 `PROVIDER_UNAVAILABLE` until a real retriever
is configured. Existing `/v1/memories/search` and MCP keyword behavior remain unchanged.

The gateway validates scope/conditions/time and liveness. The service also compares every returned
card's content, IDs, version, metadata, and source references against fresh authorized rows under
the owner lock. A live UUID cannot authorize fabricated content. New endpoint input/storage/provider
errors use safe code/retryability, and request bodies are bounded before JSON parsing.

## Preserving an existing PostgreSQL 18 volume

Compose now pins `pgvector/pgvector:0.8.7-pg18-trixie`, matching the original PostgreSQL 18 image's
Debian family and `/var/lib/postgresql` mount. Keep the existing `postgres_data` volume. These steps
assume PostgreSQL 18; a different major version needs its own PostgreSQL upgrade procedure.

Before switching images, take and verify a logical backup. The ignored `.contextbridge` directory
can hold a local backup, which contains private memory data:

```text
docker compose exec -T db pg_dump -U contextbridge -d contextbridge -Fc -f /tmp/contextbridge-before-vector.dump
docker compose cp db:/tmp/contextbridge-before-vector.dump .contextbridge/contextbridge-before-vector.dump
```

Restore a copy into an empty dedicated database such as `contextbridge_restore_test` with
`pg_restore -U contextbridge -d contextbridge_restore_test /path/to/backup.dump`, and inspect
known memories/history before relying on the backup. Keep backup files out of Git. Do not run
truncating pytest fixtures against a valuable restored copy.

After backup verification:

```text
docker compose stop api
docker compose build migrate api
docker compose up -d db
docker compose run --rm migrate
docker compose up -d api
docker compose exec -T db psql -U contextbridge -d contextbridge -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
```

An existing non-superuser migration role may need a database administrator to install/enable the
extension first. Preserve the volume on startup errors; inspect the PostgreSQL logs, image major/OS,
and port binding. The TCP health check waits for the final server, rather than the temporary
socket-only initialization server. Never remove a data volume to obtain an empty healthy database.

## Validation and remaining integration

Local full suites on real pgvector PostgreSQL 17 and 18 each passed 246 tests with 95% coverage
and no skips. Ruff lint/format, lock consistency, schema drift, and preservation migration tests
passed.
A disposable original-image → pgvector image upgrade kept the same PostgreSQL 18 volume and
preserved explicit memory/history. Core-only migration/fallback and a logical backup/restore
also passed; all probes used dedicated test databases.

CI keeps native Windows core checks and adds real vector-container checks on 17/18;
`CONTEXTBRIDGE_REQUIRE_VECTOR=1` makes a missing extension fail those jobs. Core-only Windows
explicitly skips the three numerical vector tests with a reported reason. These Linux-container
results do not establish Windows Docker Desktop or real model/agent quality; those gates remain pending.

References: [pgvector exact search, filtering and installation](https://github.com/pgvector/pgvector),
[PostgreSQL binary-string hash functions](https://www.postgresql.org/docs/18/functions-binarystring.html).
