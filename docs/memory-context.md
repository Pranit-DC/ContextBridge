# Labelled history and conflicting evidence

`POST /v1/retrieval/context` and the additive MCP tool `memory_context` provide
opt-in context around a previously retrieved memory. Standard search/retrieval
continues to return only versions applicable at the requested time. Original V1
search messages and all nine preceding tool payloads remain unchanged. Restart
the API/MCP processes after installing the feature to expose the tenth tool.

## Historical graph context (#13)

For a SQLite version that supersedes PostgreSQL, explicitly request context:

```json
{
  "memory_id": "11111111-1111-4111-8111-111111111111",
  "scope": "project",
  "project_id": "contextbridge",
  "include_history": true,
  "verify_conflicts": false,
  "depth": 1,
  "limit": 3
}
```

The seed item describes SQLite. Following its directed `supersedes` edge returns
PostgreSQL with `role: historical`, `status: SUPERSEDED` and
`applicable_at_query: false`. Edge endpoint version IDs make the chain traceable.
Historical context is not promoted to current truth. At an explicit past `as_of`,
the seed can itself be an older stored version: applicability refers to the
requested instant, not today's state. `expected_version` optionally fences the
selected version number at that instant.

Traversal follows only decreasing supersession versions of the authorized seed
memory. It preserves the seed's owner/scope/project/conditions and rejects foreign,
future, inactive or missing seeds. A retired memory requires an `as_of` inside its
previous validity interval. This endpoint never follows arbitrary cross-project
edges or reactivates retired content.

## Selective conflicting-evidence checks (#15)

Set `verify_conflicts: true` to check the seed and its eligible conflicting peers
against their original stored evidence. Both endpoints must be applicable at the
same requested instant and have identical owner, scope, project and conditions.
No evidence calls occur for ordinary nonconflicting context, history alone, or
the default false flag. Conflicting context is listed ahead of optional history.

Each item has an `evidence_check` of `not_requested`, `supports`, `contradicts`,
`insufficient` or `unavailable`. These are source-support judgments, **not truth
verdicts**. Even if both original statements are supported by their own evidence,
their conflict remains `verification: uncertain`. The check never picks a winner,
rewrites a record or changes its contested state. Full source evidence remains
available through authorized inspection; context contains source references.

The built-in Groq context judge uses the same selected model, account-wide quota
and paid-provider restrictions. Its gate can wait up to seven seconds per request
for pacing/capacity; normal interactive search retains its existing fail-fast gate.
There are at most four checks including the seed, with no retries. The first
failure stops further requests and produces uncertainty/warnings. Expensive or
quota-constrained evidence can remain unchecked; it is never silently truncated.
Synthetic HTTP tests cover successful support/contradiction/insufficiency and safe
HTTP 400, malformed response and timeout behavior. No live-model quality approval
is inferred.

Provider calls run outside memory-owner locks. The complete selected snapshot is
revalidated before each check, after built-in quota waiting and before returning
any content. A concurrent change returns safe 409; a missing/forgotten seed returns
404. Forgetting during quota waiting prevents the next hosted request. Guard hooks
are restored after use, and no transcript/evidence cache or separate memory store
is introduced.

Custom factories may optionally supply `IntegrationBackends.context_evidence_judge`;
otherwise their existing evidence judge is reused. Request-scoped provider
instances should retain the existing factory freshness convention. The API's
optional `context_verifier` injection is separate from normal search verification.

## Bounds, scope and MCP

The HTTP limit is 1–10 items including the seed; MCP limits it to five, default
three. Depth is 1–3 edges. Omission warnings identify truncated history/conflict
sets. Output is bounded to 12,000 UTF-8 JSON bytes. Long claims are replaced by a
whole-claim omission marker and `content_omitted: true`, never a misleading prefix;
full inspection preserves the original text. Size selection happens before paid
verification, with space reserved for check warnings. These are byte/character
bounds, not token counts. Unrepresentable seed metadata fails safely.

Bearer authentication and configured developer ownership apply. Project and
condition/time filters apply before relationship limits. Developer-global seeds
require explicit developer scope or `include_developer` opt-in. The MCP adapter
binds its configured project, rejects forged scope/time/history/edge replies and
has no database connection. `memory_context` is read-only for memories but its
explicit verification flag can send stored evidence to the configured provider.
The existing Streamlit inspection UI is unchanged; this endpoint is available in
the API documentation and through MCP, not a new viewer button.

## Keyless category safety (#5)

The built-in hosted interpreter cannot compare different memory types. Its shared
runtime boundary now defers cross-category relationships when either property key
is missing or the keys agree. It no longer treats missing-key PostgreSQL/SQLite
claims as proven unrelated and stores a second clear fact. The existing strict
xfail is replaced by three ordinary storage regressions. Known distinct-property
facts and capable injected interpreters retain their existing behavior.

This fixes the unsafe write through abstention. General semantic conflict
classification remains subject to evaluation; no recency/confidence winner or
metadata rewrite is added, and no teammate-owned formation module is modified.

## Verification

Focused API, hosted-adapter replay, real MCP subprocess and gateway checks cover
history labels, scope/conditions, both evidence sources, budgets, concurrent
forgetting (including quota waits), full inspection and the keyless regression.
Provider responses are synthetic; storage and protocol processes are real.
Final combined checks (29 October 2026): **1,560 passed**, no skips or xfails,
88% coverage, and 17 existing Alembic configuration deprecation warnings.
The run used dedicated PostgreSQL `contextbridge_context_test` and isolated
Redis database 15, including real Linux worker and MCP subprocess checks.
Ruff check, Ruff format check (371 files), locked dependency validation,
migration upgrade and `alembic check` passed. No schema migration was needed.
Actual hosted quality and independent acceptance remain pending.
