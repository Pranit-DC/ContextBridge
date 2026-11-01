# Memory compaction

## Exact duplicates

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
preserves every fact sufficiently to replace its sources. Independent summary-quality acceptance remains open; the bounded paraphrase path
below handles complete semantic duplicates.

Regressions exercise preview/confirm, active-count reduction, history/evidence,
restore/forget, scope/version/plan fences, incompatible batches, contested/derived
inputs, affected-summary invalidation and rollback after cleanup failure. A blocked
injected consolidation provider also verifies that foreground writes, compaction
and status checks finish before provider release. Its five-second deadlock guard
is not an approved production latency target or a hosted concurrency benchmark.


## Complete paraphrases

In the local workspace open **Activity → Merge repeated knowledge → Review current
memories**. Choose the complete memory to keep and up to four redundant memories.
The interface shows each selected claim and its full evidence. For different wording,
select **These say the same thing in different words**, allow that online preview,
and choose **Preview merge**. Check the retirement count, then **Confirm merge**.
The viewer's Maintenance tab provides the same controls. The UI lists up to 100
current, unconditional project memories; explicit API callers may choose other
compatible scoped/conditional records. No provider call runs merely by opening it.

`POST /v1/maintenance/compact-semantic` accepts the exact request above, at most
four `retire` references, and `"allow_online_verification": true` for a preview.
This is a separate additive contract; existing exact-compaction clients are unchanged.
The configured guarded Groq adapter makes at most **one** request, with no retry,
checking full bidirectional equivalence and support from each source's own user/tool
evidence. Partial overlap, extra qualifiers, different numbers/units/negation,
tentative claims and unresolved ambiguity must not pass. Unsupported, uncertain,
missing, duplicate, unexpected or malformed verdicts never issue approval.

Type, conditions, claim key, confidence, current validity and scope must match;
content alone may differ. Contradicted, contested, derived, retired and event/state/
lesson inputs remain ineligible. V2 temporal contracts must match too, including
precision/ranges. Both exact and semantic preview hashes include that time metadata.
The batch's serialized source records are capped at 16,000 UTF-8 bytes, with the
existing account token/daily ceilings also enforced; oversized batches are refused,
never truncated. Try fewer sources when quota capacity is insufficient.

An accepted preview returns the existing plan fields plus `verification_token`.
Confirm using the same source IDs/expected versions, `"confirm": true`, the returned
`plan_revision` and `verification_token`. Confirmation makes **zero** provider requests.
The token is server-signed, bound to owner and the full plan, expires after ten minutes,
and contains hashes/time only. It becomes invalid after API-process restart; preview
again. The supported single-process local API is the signing authority; deploying
multiple independently signed API processes would require session affinity or a
separate shared signing-key design, which is not the current deployment.

No database transaction/row/owner locks remain open during verification or quota
waiting. Sources and derived closures are rechecked before the request (again after
quota waiting), after the response, and under the confirmation transaction. Changed
or forgotten inputs cannot be retired or resurrected by a stale preview. No transcript,
model response, approval content cache, hidden evidence backup or new durable table
is introduced. Retirement, restoration, historical inspection, derived invalidation,
index cancellation and permanent forgetting use the same shared lifecycle service.

Automated evidence: `tests/integration/test_semantic_compaction.py` includes actual
workspace widgets → HTTP client → API → QuotaClient/ChatCompactionVerifier with
scripted HTTP → PostgreSQL, plus stale plan, owner/scope/version, expiry/tamper/restart,
time precision, quota-wait forget, post-response change, foreground progress and
rollback regressions. These establish integration and safety behavior, not actual
model equivalence accuracy. Live provider and independent representative quality/
faithfulness/performance acceptance remain separate; no live calls were authorized
or made for this follow-up.
