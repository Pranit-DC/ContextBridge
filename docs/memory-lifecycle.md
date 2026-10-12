# Retire, restore and forget

Retirement stops current use and preserves every stored version/evidence. Restoration copies a
selected historical version into a **new** current version with fresh user/tool evidence. The old
validity interval stays closed, including the gap when the memory was retired. Forgetting permanently
removes the stored memory and related content; a forgotten memory cannot be restored.

The seven existing MCP tools retain their inputs/results. Two additive tools are available:

- `memory_retire(memory_id, expected_version)` requires an explicit user request.
- `memory_restore(memory_id, expected_version, source_version, source)` requires fresh user/tool
  evidence. Inspect after a lost response before retrying; a repeat does not create another version.

The new HTTP management messages do not change common contract V1:

| Action | Endpoint | Required body |
| --- | --- | --- |
| Retire | `POST /v1/memories/{id}/retire` | scope/project and expected_version |
| Restore | `POST /v1/memories/{id}/restore` | same, source_version number and Source evidence |
| List retired | `POST /v1/inspection/retired` | scope/project; optional conditions, include_developer, cursor, limit |
| Lifecycle state | `GET /v1/memories/{id}/lifecycle` | none |
| Configured features | `GET /v1/status` | none; configuration only, no paid/provider probes |

All endpoints require the existing token and configured owner. Mutation bodies bind scope/project;
MCP still checks its project before sending a mutation. Retired listing uses bounded keyset pages,
filters conditions before limits, and never broadens the caller's scope. Old inspection returns the
same response shape and the closed current version as SUPERSEDED. Historical searches still return
versions applicable at the explicitly requested time.

Retiring a source also retires its bounded transitive derived summaries. It cancels affected index/
consolidation/capture jobs and clears this owner/project scope's buffered imports conservatively,
because unprocessed transcripts do not yet have reliable fact-level provenance. Other owners and
projects remain untouched. Existing historical vectors are preserved. Restoration queues discovery
for the new version; it does not reopen cancelled old work.

Built-in semantic import resolution defers references to retired claims; only explicit restoration
can reactivate the same memory. Unrelated supported facts may still be imported. Corrections and
new conflicts close stale derived summaries atomically with the source change. Original memories
and summary history remain available. Generated summaries must be rebuilt from current sources
through consolidation; they cannot be restored directly. Restoration retains contested state and
does not silently settle an existing conflict.

The additive `914ed026bb32` migration adds nullable retirement time to existing memories. Existing
data starts unretired. Upgrade is explicit; downgrade/round-trip checks run only on disposable `_test`
databases. Source content is never copied into retirement metadata.

Validation: full isolated PostgreSQL/Redis suite **1242 passed, no skips**. After the final
same-import cancellation adjustment, 33 focused lifecycle/write-engine tests passed. Ruff
lint/format, frozen lock, schema drift and retirement migration round-trip checks passed.
Discovery tests now cover nine tools while preserving the original seven. No live model calls
were made during this stage. Provider PR #30 precedes this dependent lifecycle stage.
