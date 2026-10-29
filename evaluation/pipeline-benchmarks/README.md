# Offline retrieval, ranking and compact-context comparison

This delivers reproducible benchmark tooling for remaining-work **#12, #14 and
#16**. It tests the assembled retrieval service, actual PostgreSQL/pgvector
channels, fusion, stored-field validation, conflict policy and context budget.
It makes **no hosted requests**. Four-dimensional vectors are authored fixtures;
they are not outputs from an embedding model and cannot establish semantic quality.

## Recorded result

[Raw result](offline-20261029.json), [case labels](cases.json),
[runner](../../scripts/benchmark_memory_pipeline.py).

The run contains **17 design cases and three scale probes**, each compared in
five modes: 100 rows, with all recorded design checks passing. Each mode has one
unmeasured warmup and five timed repetitions. Cases are partitioned into development
and `holdout_design`; both partitions are synthetic, authored by the implementer,
and pending independent review. No held-out real-world accuracy is claimed.

| Probe | Observed behavior |
| --- | --- |
| Paraphrase | Keyword returns nothing; the fixture vector channel finds the authored database match |
| Unresolved alternatives | Fusion places disputed database choices first; ranking moves the clear port fact first and retains both uncertain alternatives |
| One-card conflict limit | A disputed card remains uncertain and the missing-alternative warning is retained |
| Current/history | Current correction and historical original return the expected version |
| Scope/conditions/deletion | Forbidden owner/project/environment/deleted records do not return |
| Missing/stale vector | Vector-only has no match; hybrid returns the lexical current fact with explicit degradation |
| Qualified long claim | Whole claim is omitted with a marker; complete text and evidence remain inspectable |
| Multibyte text | Size accounting uses UTF-8 serialized bytes, not character counts alone |
| Total context capacity | Eight source cards become six cards, 14,891 → 11,208 bytes; omissions are explicit |

For the qualified long claim, compact context is **673 versus 2,734 bytes** with
ranking alone. This does not mean the answer is equally useful: the report also
counts full claims remaining in context. A marked omission requires inspection.

| Distractors in queried project | Compact hybrid p50 | p95 |
| --- | ---: | ---: |
| 0 | 8.912 ms | 11.097 ms |
| 100 | 13.878 ms | 14.417 ms |
| 500 | 21.202 ms | 21.402 ms |

These timings cover in-process service calls and real loopback PostgreSQL, with
four-dimensional fixture vectors and warmed caches. Earlier cases remain in
separate projects until final cleanup; these counts describe added distractors in
the queried project, not total database rows. They exclude HTTP/MCP transport,
real embedding/model latency, quota waits, cold startup and concurrent production
load. Five samples make p95 the sample maximum. They establish a repeatable small
probe, not a production latency target or larger-store acceptance.
The runner reuses a SQLAlchemy session; fresh-request session/connection overhead
is not separately measured.

## Repeat safely

Use an empty, migrated, dedicated pgvector PostgreSQL database ending in `_test`.
Do not run this alongside the pytest suite, workers or another database writer.
The runner refuses non-test URLs, non-PostgreSQL databases, existing memory/capture/
job/model records, missing pgvector, invalid repetition/scale bounds and existing
output files. Use the README's test-database migration instructions first.

```bash
uv run python scripts/benchmark_memory_pipeline.py \
  --output /tmp/new-pipeline-benchmark.json --repeats 5 --scale 500
```

The URL comes only from `CONTEXTBRIDGE_TEST_DATABASE_URL`; it is not included in
the report or error messages. The script uses the real explicit-write, correction,
indexing, inspection and forget services. Fresh synthetic owner/project identities
isolate each run/case. Cleanup forgets only created memories and deletes only that
run's indexing jobs/outbox/model metadata, including after provider/index failure.
It never truncates the database. Abrupt process termination can leave synthetic
test records; rerunning then refuses the nonempty store rather than deleting them.

The output records dataset/runner SHA-256 fingerprints, timestamp, PostgreSQL and
Python versions, exact returned labels, warnings, per-case checks, byte sizes,
fixture embedding-call counts and individual timing samples. A failed design check
still writes an inspectable report and returns a nonzero exit status. Report JSON
is evidence, never executable input. No provider credentials, evidence contents,
private database URLs or fabricated dollar/token estimates are recorded.

## Compare modes and interpret metrics

- `keyword`: actual PostgreSQL lexical + symbolic channels; no embedding call.
- `semantic`: actual pgvector distance over fixture vectors, other channels disabled.
- `hybrid_fusion`: all channels with the existing fusion policy, no added conflict
  ranking or context compaction.
- `hybrid_ranked`: same channels plus the production conflict policy.
- `hybrid_compact`: same channels, ranking and production context budget.

All modes use the same stored eligibility and liveness checks, candidate pool,
query filters and result limit. Graph expansion and evidence verification are off
in this comparison; their quality/cost requires separate evaluation. Baseline
mode switches live only in this script and do not change application behavior.

Selection precision is relevant returned IDs / returned IDs; recall is relevant
returned IDs / all relevant IDs; reciprocal rank is the first relevant position's
inverse. An empty return has undefined precision, and a no-relevance case has
undefined recall/MRR plus a separate correct-abstention result. Macro summaries
exclude undefined metrics and disclose the number of defined cases. Recall can be
below one for a deliberate result-size or byte limit. Relevance metrics assess
selected memory identities, not generated-answer quality or omitted-claim usefulness.

Design checks include no forbidden IDs, correct versions, bounded result count,
stable repeated results, uncertain disputes, missing-index warnings, explicit
omissions, full source inspection and final byte bounds. Hybrid compact selection
must recover the authored minimum relevant count; capacity cases explicitly permit
omission. No confidence, similarity or recency score selects a factual winner.

## Remaining acceptance

Independent reviewers must approve or correct relevance labels and define actual
quality, latency and cost targets before tuning. Fresh representative real-model
development and holdout sets, provider/transport timing, realistic embedding
dimensions, larger stores and load remain pending. Zero hosted requests is the
measured cost observation; fixture-call counts are not paid-provider cost estimates.
This work does not resume the stopped live-provider ledger or approve overall
#12/#14/#16 completion.

Verification: **1,569 tests passed**, no skips or xfails, 88% coverage. Ruff check,
format check (375 files), locked dependency validation, dedicated test-database
migration upgrade and schema drift check passed. Real Linux/Redis worker probes
and MCP subprocess tests ran. Seventeen warnings are existing Alembic configuration
deprecations. The benchmark's nine new tests cover metric denominators, safe
refusal/error output, real mode comparisons and successful/failing cleanup.
