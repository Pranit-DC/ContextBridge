# Retrieval policy (H1)

`contextbridge.retrieval.Retriever.search(query, repository, embedder, verifier)` turns a
`RetrievalQuery` into a `RetrievalResult` of compact cards, using the shapes in
[contracts V1](../team-plan/contracts-v1.md). It owns no memory store: all reads go through the
injected repository, and it makes no database, network, or model call itself.

## Status

| Part | State |
| --- | --- |
| Query validation, fusion, applicability checks, cards, degradation | Implemented and tested with fakes |
| Real embedding model, evidence verifier, graph expansion | Pending (H2) |
| Real repository (PostgreSQL channels, pgvector) | Pending; Pranit owns it, see [integration request](integration-request.md) |
| `POST /v1/retrieval/search` endpoint, MCP card adaptation | Pending; Pranit owns them |
| Measured quality against the keyword baseline | Pending (H4) |

The `verifier` argument is accepted so the agreed signature is stable, but it is **not called**.
Every card reports `verification: "not_requested"`. Nothing here is semantic retrieval until a real
repository serves the `semantic` channel with a real embedder; tests use fakes that prove policy only.

## What a search does

1. **Validate** the query. Secrets, bad limits, naive timestamps, unknown fields, or the wrong
   `schema_version` raise `ModuleError("INVALID_INPUT")` with no echoed input. Only whitespace is
   normalized, so identifiers and paths survive. `as_of` defaults to the current time, fixed once
   for every stage. Scope, project, conditions, and limit are never changed or inferred.
2. **Embed** the query text once. Failure or malformed output (wrong count, size, or non-finite
   numbers) skips the semantic channel and adds `EMBEDDING_UNAVAILABLE`.
3. **Ask each channel** (`lexical`, `semantic`, `symbolic`) for at most `channel_limit` matches.
   The lexical channel failing raises a retryable `STORAGE_UNAVAILABLE`; the others degrade.
4. **Re-check every match.** Whatever the repository returns must still match the caller's
   project (or developer scope with `include_developer`), every stored condition, and the effective
   interval `[valid_from, valid_to)` at `as_of`. Malformed or mislabelled matches are dropped.
5. **Fuse** with reciprocal rank fusion: a version scores `sum(1 / (k + rank))` over the channels
   that returned it, at its best rank in each. Raw channel scores are not used because they are not
   comparable. Duplicates collapse by version ID. Order is project before developer memory, then
   score, then newer memory, then version ID, so ties are deterministic.
6. **Check liveness** of each candidate in order and stop at the caller's `limit`. A record that is
   not live is skipped and the next candidate takes its place. If liveness cannot be checked, the
   record is withheld (fail closed) and `LIVENESS_UNAVAILABLE` is reported.
7. **Return cards** with source references only; full evidence needs inspection.

Contested memories keep `decision_state: "contested"` on their card. No card is ever invented to
fill a slot: an empty result returns `cards: []` and the warning `NO_RESULTS`.

## Warnings

`degraded` is true when any warning ends in `_UNAVAILABLE`.

| Warning | Meaning |
| --- | --- |
| `EMBEDDING_UNAVAILABLE` | Query embedding failed; semantic search was not used |
| `SEMANTIC_UNAVAILABLE`, `SYMBOLIC_UNAVAILABLE` | That channel failed; results come from the others |
| `LIVENESS_UNAVAILABLE` | A candidate could not be confirmed live and was withheld |
| `INVALID_MATCHES_DROPPED` | The repository returned malformed or wrongly labelled matches |
| `NO_RESULTS` | Nothing applicable and live was found |

These warning codes are this module's own; they extend the shared vocabulary only for retrieval
results. Pranit's adapter should pass them through or map them deliberately.

## Configuration

`RetrievalConfig(rrf_k=60, channel_limit=50)`. `rrf_k` damps the advantage of top ranks and
`channel_limit` bounds each channel (1 to 100). Both are starting values and have not been tuned;
H4 should evaluate them on a holdout set before anyone relies on them.

## Tests

```text
uv run pytest tests/retrieval
```

The fake repository deliberately returns unfiltered, out-of-scope, stale, and malformed records
to exercise the defensive checks. Passing these tests shows the policy is correct; it does not
show real SQL, vectors, or model quality.
