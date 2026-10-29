# Exact-claim compaction

`POST /v1/maintenance/compact` previews and explicitly confirms retirement of
selected redundant memories. It reduces current searchable records while keeping
all original evidence, versions and historical validity. It never deletes or
rewrites source claims, and makes no model request.

Choose a retained memory and up to 19 duplicates, all in one exact owner, scope,
project and condition set. Current clear source FACT, PREFERENCE and DECISION
records must have identical content, type, claim key and confidence. Events,
derived inputs, retired/expired sources, disputed claims and memories with
contradiction edges are refused. Similar wording is insufficient.

Send this authenticated request to preview:

```json
{
  "scope": "project",
  "project_id": "contextbridge",
  "keep": {"memory_id": "RETAINED_UUID", "expected_version": 1},
  "retire": [{"memory_id": "DUPLICATE_UUID", "expected_version": 1}]
}
```

Inspect the returned `affected_memory_ids`, including summaries derived from the
selected duplicates. Confirm with the identical request plus `"confirm": true`
and the returned `"plan_revision"`. Preview performs no cleanup. Confirmation
rechecks every selected version and the complete bounded closure under the owner
transaction lock; changed records or newly affected summaries require a fresh
preview. There is no automatic batch discovery or unattended semantic retirement.

The one transaction closes validity intervals, retires affected summaries and
cancels affected capture/index/consolidation work. Any failure rolls back the whole
operation. At most 200 memories may be affected. The retained original remains
active. Summaries invalidated by retirement must be rebuilt through consolidation;
they are never silently reattached to another source. Historical search and
inspection preserve the originals. Restore requires the normal fresh evidence;
permanent forget retains its existing full-erasure behavior. After a lost response,
inspect lifecycle status before attempting a new preview.

This is conservative exact-claim compaction, not a claim that a generated summary
preserves every fact sufficiently to replace its sources. Arbitrary semantic
compaction and independent summary-quality acceptance remain open.

Regressions exercise preview/confirm, active-count reduction, history/evidence,
restore/forget, scope/version/plan fences, incompatible batches, contested/derived
inputs, affected-summary invalidation and rollback after cleanup failure. A blocked
injected consolidation provider also verifies that foreground writes, compaction
and status checks finish before provider release. Its five-second deadlock guard
is not an approved production latency target or a hosted concurrency benchmark.
