# Automatic related-memory links

ContextBridge now creates `related_to` navigation links as supported memories are
saved. For example:

- FACT: "The database schema is in `db/schema.sql`."
- STATE: "Review `db/schema.sql` before deployment."

If both original evidence excerpts also contain that exact code reference, saving
the second memory links the two versions. Searching for a distinctive term from
the first memory can then include the second through existing graph expansion.
Inspection exposes the edge and each endpoint's original evidence.

## What qualifies

The rule is deterministic and makes no model requests. A reference must appear
in single backticks in **both** the memory content and its evidence. It must be
an exact, case-sensitive structured identifier/path (for example `db/schema.sql`,
`database_url`, `/v1/memories`) or CamelCase name (for example `DatabaseConfig`).
Generic words, prose similarity, model confidence and claim-key equality do not
create these links. A path is a reference only; the linker never opens it.

`related_to` means "these memories cite the same code reference", not "these
claims are true, equivalent, or one supersedes the other". Conflicts, corrections
and derived summaries retain their specific existing edge types. This feature is
conservative identifier-based linking, not general semantic relation inference.
Useful semantic relationships with no qualifying reference will not be linked.

Only clear, current, active, non-retired versions with the same owner, scope,
project and complete condition set qualify. Memory types may differ, so a database
fact and a migration state can link. The original evidence remains unchanged.

## Transactions and bounds

Automatic linking runs on explicit saves/corrections, imported candidate writes,
restoration and consolidation, inside the same transaction as the version write.
An owner lock serializes it with updates, other linkers and forgetting. A failure
rolls back the version and links together. Existing write/capture replay identities
remain unchanged. Related edges use canonical endpoint ordering; expansion works
in either direction. Existing direct edges of any kind suppress a redundant generic
link. No new schema, migration, public endpoint or common message field is needed.

Each run considers at most eight evidenced references and 100 matching candidate
versions, ordered by newest recorded version then version UUID. Each endpoint
receives at most eight automatically created `related_to` edges. These are bounded
candidate/result limits, not a guarantee of constant database scan time. This can
omit useful neighbors in large stores; it never claims to construct a complete graph.
Existing manually inserted edges are not removed to satisfy the automatic cap.

Corrections and restoration reevaluate fresh content/evidence. Old version edges
remain historical and obey retrieval's effective-time checks. Retiring a memory
removes it from current expansion. Forgetting cascades through its version edges
without deleting an unrelated neighbor; backfill cannot recreate a deleted endpoint.
The existing current-time restriction on historical traversal remains unchanged.

## Existing records

Run the bounded backfill explicitly with the normal service configuration:

```bash
uv run python -m contextbridge.engine.related_cli --project-id contextbridge --limit 100
```

The command prints only `processed`, `links_created` and `next_cursor`. Repeat
with `--after UUID` using the returned cursor until it is null. A final empty page
is possible. Use `--developer` instead of `--project-id` for explicitly selected
developer-global memories. Each page commits atomically and is safe to repeat.
Concurrent writes with UUIDs before the cursor can require another pass from the
beginning; the cursor is bounded progress, not a database snapshot.

No existing database is backfilled merely by installing the change. New writes
create links automatically; this command is for records saved before the feature.
Database exceptions, evidence and credentials are not printed.

## Retrieval and testing

Related neighbors appear only when graph expansion is enabled and result slots
are available. The existing runtime enables it with formation or
`CONTEXTBRIDGE_RETRIEVAL_EXPAND_GRAPH=true`. A lexical query never gains a semantic
label because a related edge was followed.

`tests/integration/test_related_links.py` exercises automatic save → persisted
edge → inspection → real repository/retriever expansion → forget, plus import
replay, isolation, version updates/restoration, concurrency, rollback and backfill.
It uses real PostgreSQL and no hosted providers. Policy/CLI failure checks are in
`tests/engine/test_related_policy.py`. Model-quality/retrieval benchmark approval
remains the other workstream.

## Verification — 29 October 2026

- Final full all-extras suite: **1,473 passed, zero failures/errors/skips**, with
  87% parent-process coverage. All 17 warnings are the existing Alembic
  `path_separator` deprecation. Real Linux Redis/prefork probes ran.
- Ruff lint and formatting checks, frozen lock check and diff whitespace passed.
- Alembic upgrade and schema drift check passed; migration preservation and
  downgrade/upgrade regressions ran in the full suite. No migration is added.
- All database checks used only the disposable `contextbridge_related_test`
  PostgreSQL 18/pgvector database. Redis used an isolated loopback broker, DB 15.
  Existing application databases and credentials were not changed.
- Earlier full-suite verification exposed a pre-existing graph warning failure,
  reproduced independently on untouched develop at `3e84ec9`. The shared retrieval
  boundary now drops `RELATED_MEMORIES_INCLUDED` if final ranking/size limits
  remove every graph-only result. It makes no extra search/provider calls and
  changes no public contract or teammate-owned module.

Tests used the existing locked environment (`uv run --no-sync`, with all extras
for pytest). These results prove deterministic linking, persistence and retrieval
mechanics; no hosted model accuracy, semantic link inference or general retrieval
quality improvement is claimed. The created test containers were disposable.
