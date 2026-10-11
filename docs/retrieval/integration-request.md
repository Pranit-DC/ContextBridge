# Integration requests to Pranit (retrieval)

Shared-file changes this module needs. Nothing here has been implemented outside
`src/contextbridge/retrieval/`.

## 1. Repository for the three channels

Implement the `RetrievalRepository` protocol in `contracts/interfaces.py` against PostgreSQL.

- `search_channel(channel, query, query_embedding, limit)` must apply owner, project, conditions,
  and effective-time filters **before** choosing results, and return `RankedMatch` dictionaries:
  `{record, channel, rank}`, `rank` starting at 1, `channel` equal to the requested channel.
  The retriever drops any match that violates the query anyway, but a repository that filters
  after ranking can hide every valid hit behind out-of-scope ones.
- `semantic`: `query_embedding` is `{model_id, dimensions, vector}`. Return nothing, or raise,
  for a stored model/dimension mismatch; do not compare incompatible vectors.
- `symbolic`: exact identifier matching (file paths, function names, config keys). The retriever
  sends the caller's query text with whitespace collapsed and nothing else changed.
- `is_live(version_id, query)` is called for each returned candidate, with the same query. It must
  be true only if the version still exists and is applicable at `query.as_of`. Deleted memories
  must return false, including while an index is stale.
- Each call receives `query.as_of` already resolved to a timestamp.

## 2. Endpoint and MCP

- `POST /v1/retrieval/search` could call `Retriever().search(...)` as agreed in contracts V1.
  `ModuleError` carries `code` and `retryable` for the `{detail: {code, retryable}}` response:
  `INVALID_INPUT` (422) for a bad or secret-containing query, `STORAGE_UNAVAILABLE` (503,
  retryable) when the lexical channel fails.
- The result's `warnings` are listed in [README](README.md#warnings). The MCP adapter should show
  `degraded` and `NO_RESULTS` rather than hide them.

## 3. Not needed yet

pgvector, an embedding provider setting, and a UI dependency are not required for H1. They are
requested separately with exact dimensions and index needs when H2 chooses a model.
