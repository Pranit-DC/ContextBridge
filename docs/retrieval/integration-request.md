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
- `is_live(version_id, query)` is called for each returned candidate and each related record, with
  the same query. It must be true only if the version still exists and is applicable at
  `query.as_of`. Deleted memories must return false, including while an index is stale.
- Each call receives `query.as_of` already resolved to a timestamp.

## 2. Inspection and graph expansion

- `inspect(memory_id, query)` returns the existing `InspectionResponse` (memory, full history with
  evidence, edges), authorized for the configured developer and the query's project. It is called
  only for the few cards that need verification. Out-of-scope or absent IDs must raise or return
  nothing, never another project's memory.
- `expand(version_ids, query, limit)` returns `MemoryRecord` dictionaries related to the given
  **version IDs** (edges use version IDs, not memory IDs). Please apply scope, conditions, and time
  to every record it returns, keep it to same-scope valid relationships, and stop at `limit`. The
  retriever re-checks all of this and handles cycles itself, so this is for efficiency, not safety.
  Relationship types worth following first: `supersedes` and `contradicts`.

## 3. Vector storage (when H2 picks a model)

Not requested yet, because no model is chosen. When it is, I will send the exact model ID, vector
size, and normalization. What the repository must do:

- Store the model ID and dimensions with every vector, version-linked, and never compare vectors
  from different models. Reindex on a model change.
- Use bounded exact search first, and keep scope/time/condition filters before ranking, so an
  approximate index cannot hide every valid hit.
- Remove vectors together with the memory they belong to when it is forgotten.

`RetrievalConfig.embedding_model_id` and `embedding_dimensions` should be set from the same
configuration so queries are only embedded with the model the stored vectors were built with.

## 4. Endpoint and MCP

- `POST /v1/retrieval/search` could call `Retriever(config).search(...)` as agreed in contracts V1.
  `ModuleError` carries `code` and `retryable` for the `{detail: {code, retryable}}` response:
  `INVALID_INPUT` (422) for a bad or secret-containing query, `STORAGE_UNAVAILABLE` (503,
  retryable) when the lexical channel fails.
- The result's `warnings` are listed in [README](README.md#warnings). The MCP adapter should show
  `degraded`, `NO_RESULTS`, and `RELATED_MEMORIES_INCLUDED` rather than hide them.

## 5. Decisions and contract questions

- **Related marker.** Cards cannot say they came from graph expansion rather than a direct match.
  A `via: "direct" | "related"` card field would fix that. It is a contract change, so I have not
  made it; until then expansion stays off by default and is disclosed through a warning.
- **Dependencies.** A real embedding model needs a dependency in `pyproject.toml` and `uv.lock`,
  which Pranit owns. The model choice itself is a team decision (see the README).
- **Judge.** A real `EvidenceJudge` needs a provider choice, and any hosted provider would send
  stored evidence off the machine. That needs explicit approval before I build it.
- **Verification trigger.** Which memory types count as high-impact (`verify_types`) is a product
  decision. It is empty by default.
