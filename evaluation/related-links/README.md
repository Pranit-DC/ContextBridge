# Related-link integration comparison

This small offline comparison tests #8's explicit shared-reference rule, not a
general semantic model. All records are synthetic. Expected relevance labels are
**design cases pending independent review**, not approved quality ground truth.

The real PostgreSQL store, automatic linker, shared retrieval service and actual
retriever run twice: direct lexical search, then lexical search with graph
expansion. No model response or vector relevance is simulated. Embedding support
is unavailable explicitly; there are **zero hosted requests**.

| Case | Direct results | With graph | Design expectation |
| --- | --- | --- | --- |
| Migration/schema context | decision | decision, deployment procedure | Add the procedure citing the same evidenced path |
| Configuration context | configuration | configuration, validation rule | Add the rule citing the same evidenced identifier |
| Prose overlap | seed | seed | No link from generic shared words |
| Unevidenced code reference | seed | seed | Do not infer a link from invented claim text |
| Foreign project | seed | seed | Do not cross project boundaries |
| Unmatched conditions | seed | seed | Do not add production-only context |
| Foreign owner | seed | seed | Do not cross owner boundaries |
| Full one-card limit | seed | seed | Preserve the direct result and caller limit |

The [saved report](integration-comparison-20261029.json) matches all eight design
expectations. The first two demonstrate contextual additions absent from direct
search; the six controls add no unintended context. This is limited mechanistic
evidence of usefulness/noise control for the specified cases, not a measured
real-world accuracy rate or general retrieval-quality approval.

## Reproduce

Use an **empty, migrated, dedicated PostgreSQL database ending in `_test`** and
the README's normal test environment configuration:

```text
uv run python -m scripts.evaluate_related_links --output /tmp/related-links-new-report.json
```

The script reads only `CONTEXTBRIDGE_TEST_DATABASE_URL`, never falls back to the
application database, refuses a nonempty store and refuses an existing output
file. It creates isolated synthetic records and removes its records on completion
or failure. A hard process kill can leave synthetic test records; use a disposable
test database. It never truncates existing records or edits credentials.

Safety/reproducibility checks are in `tests/integration/test_related_evaluation.py`.
Lifecycle/isolation/concurrency and backfill are covered separately by
`tests/integration/test_related_links.py`. The full project benchmark remains
separate from this small #8 comparison.
