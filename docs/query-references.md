# Authorized follow-up retrieval

`memory_followup` lets a client explicitly bind a follow-up to a memory it selected
from this project's prior results. This works across configured agents and fresh
sessions without storing conversation history or a global last-query cache.

```json
{
  "memory_id": "UUID_FROM_PREVIOUS_RESULT",
  "expected_version": 1,
  "query": "Are we using it now?"
}
```

The MCP gateway stamps the configured project. The additive HTTP equivalent is
`POST /v1/retrieval/referenced-search` with `memory_id`, `expected_version` and a
nested unchanged V1 `query` object (including `schema_version: 1`, scope/project,
query text and any explicit conditions/as_of/limit). Existing search/retrieve
interfaces and all ten previous MCP tools remain compatible.

The shared service authorizes the reference against the caller's exact owner,
scope, project, conditions and query time. An explicit historical query can refer
to that historical version. Current queries reject retired or stale references.
One bounded known topic (database, runtime, cache or API) can replace `it`, `that`
or `this choice`; arbitrary stored text never becomes instructions or expansion
text. For example, the query above becomes `Are we using database now?` when the
selected source unambiguously concerns a database.

Multiple topics, conflicting explicit topics, contested records, contradiction
edges, ordering-dependent `former/latter`, missing historical/version filters and
overlong expansions defer with clarification warnings before retrieval/provider
calls. The caller's project, conditions, time and limit are never inferred or
rewritten. Ordinary retrieval still ranks current/clear evidence and preserves
uncertain alternatives. Semantic matching requires the configured embedder;
lexical fallback retains its normal limitations and degradation warnings.

Reference snapshots are rechecked under the owner lock after retrieval, including
version, retirement, content/evidence and dispute state. Forget/update during a
provider call fences the response. The authorization lock is released before
network/quota work, so unrelated operations can continue. No response cache or
persistent reference/session table is introduced.

This is explicit client-selected topic binding, not automatic interpretation of an
agent's private session history or a general pronoun/coreference model. It does
not infer the specific referent of ambiguous comparative phrases or choose which
conflicting claim is true. Representative relevance and independent review remain
quality gates, separate from the failure/scope regressions.

Tests cover the actual API/PostgreSQL path, MCP gateway and real MCP subprocesses,
reference scope/conditions/version, historical selection, original-query time
clarification, disputed edges, secret input, bounded expansion and in-flight
update/forget. Stored instruction-like text cannot expand the whitelist topic.
