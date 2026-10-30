# Multi-source evidence and source time — opt-in V2

This additive extension combines an explicitly selected group of chat turns into an
atomic memory with every contributing user/tool quote. Existing V1 events, module
interfaces, stored records and clients keep their shapes and behavior.

## Use

1. Apply migrations (`uv run alembic upgrade head`) before restarting services.
2. In local **Settings → Memory & processing preferences**, enable **Combine
   imported turns with original timezones** and normal AI processing. Save and
   apply settings. Equivalent environment flag:
   `CONTEXTBRIDGE_CAPTURE_EVIDENCE_V2_ENABLED=true` on the API and worker.
3. In **Import → Combine turns with original dates (advanced)**, paste an explicit
   V2 JSON bundle. Start with [the example](examples/evidence-bundle.json), replacing
   its project, IDs, original turns/times and IANA timezones. Do not change IDs or
   content on a lost-response retry. A new conversation needs new UUIDs.
4. Check processing progress, then inspect **Original source dates and contributing
   turns**. Accepted means queued; it does not mean a memory was admitted.

The same input works through the bounded native importer:

```bash
uv run contextbridge-import --project-id contextbridge validate-bundle bundle.json
uv run contextbridge-import --project-id contextbridge submit-bundle bundle.json
uv run contextbridge-import --project-id contextbridge status JOB_UUID
```

Configuration/authentication follow the existing importer. No live calls occur on
validation. Submission explicitly sends the chosen content to the configured
provider through the shared quota guard; no separate model/store is introduced.
The ordinary host capture hook remains V1. Enabling V2 does not silently collect
or combine private conversations from agents.

## Boundaries and evidence

`POST /v2/interactions/bundles` accepts `schema_version: 2`, a `bundle_id`, and
1–20 original V1 source events with explicit `source_timezone`. Sources must share
authenticated owner, project/scope, agent and session. Total bounds remain 20
messages/32,000 characters/512 KiB body. Original event/message IDs, offsets,
roles and source timestamps/offsets survive aliasing; source texts remain in the
existing expiring capture store. Each bundle is a frozen group in the existing
capture job/outbox system, committed atomically with its source metadata.

The integration adapter requests exact quoted user/tool fragments, checks their
origin and offsets, and independently audits all pending claims in one bounded group call, checking meaning, scope, conditions,
type and the relation of the date to the claim. Only hash/verdict pairs are cached within
the current task; live source and candidate metadata are revalidated before each verdict is reused.
Assistant suggestions, unresolved
references, foreign scope, unsupported claims, mismatched dates and invalid model
output cannot authorize durable knowledge. Every required fragment must fit the
existing evidence bound; evidence is rejected rather than silently truncated.

Committed evidence is a clearly labelled tool-produced composite, containing all
original attributed quotes. It is visible through normal inspection and retrieval
evidence. `POST /v2/inspection/provenance` and MCP `memory_provenance` additionally
return structured fragments and temporal metadata, scoped to the requested memory
and version. Legacy versions explicitly report the original format. Metadata is
not an independent hidden content archive.

## Time semantics

Each relative phrase uses its own source instant and explicit IANA timezone, never
import receipt time or a guessed locale. Original offsets remain in provenance;
normalized bounds use UTC. Supported forms include yesterday/today, last week,
numbered days/weeks ago, ISO dates/offset instants and explicit between/through
ISO-date ranges. Mixed/conflicting dates and clocks without an explicit offset defer.
Ambiguous or unsupported relative expressions defer rather than
inventing a time. Repeated/nonexistent DST wall times defer; calendar days may
last 23 or 25 hours.

- `earliest` is the lower occurrence bound; `latest` is the exclusive calendar upper bound for day/week/range precision.
- `guaranteed_from` is the conservative applicability boundary: a completed
  transition is established by the end of its interval or by source observation,
  whichever is earlier. A timeless combined claim cannot apply before its latest
  contributing observation.
- Date-only evidence retains `day`, `week` or `range` precision. The content
  explicitly states the uncertainty; no exact occurrence instant is asserted.
- A date that describes a deadline/constraint is `context_only`. It stays source
  metadata and does not retroactively start/end the stored state. A future deadline
  therefore does not become a future-effective write.
- A corrected previous state ends at the transition's lower bound; the new state
  begins at `guaranteed_from`. Ordinary historical retrieval withholds both in the
  uncertain gap. `POST /v2/retrieval/temporal-context` or MCP
  `memory_temporal_context` shows labelled `possible_before`/`possible_after`
  alternatives and `TRANSITION_TIME_UNCERTAIN`, with explicit conditions,
  expected version, scope and output limit. Contested claims stay labelled.

The V2 import requires an explicit timezone instead of supplying an implicit UTC
fallback. Ambiguous/unknown occurrence time defers; it is not admitted as a precise
state transition. Global developer imports retain the existing separate opt-in.

## Lifecycle and validation

The migration adds capture/candidate/version provenance tables without changing
existing rows. Corrections and provenance commit in one transaction. Cancellation,
raw/candidate expiry and rejection remove associated ephemeral copies. Retirement
keeps visible history; permanent forget cascades all version evidence and provenance
and cancels contributing jobs, including in-flight provider work. Restoration uses
fresh evidence and its normal version boundary rather than copying an old uncertain
transition into the present.

Tests cover real PostgreSQL/API writes and replay, independent audit outcomes,
source offsets/zones, DST/ranges, uncertain historical alternatives, scope,
tampering, feature-off queues, rejected data, expiry, deletion during provider calls,
commit rollback/restart, migration preservation, CLI, UI widgets and MCP subprocesses.
Scripted model responses establish integration behavior, not general model quality.
A separately authorized live smoke check and independently reviewed representative
quality/performance remain completion gates; the earlier stopped V1 live ledger
cannot establish this new path's provider acceptance.

V2 live attempt 1 stopped after two successful HTTP responses but failed overall
processing; see the [retained failure evidence](../evaluation/live/20261030-evidence-time-attempt1/README.md).
The ledger is stopped and cleanup passed. Bounded grouped verification is the follow-up fix;
real-provider acceptance remains open.

## Grouped audit regression

The first live attempt exposed a quota/worker-lease failure on two candidates.
The integration now audits the entire frozen candidate group once, independently
classifying each candidate and requiring an exact, unique candidate-ID response set.
The two-candidate regression verifies exactly two formation calls total (extraction
plus grouped audit), rejection cleanup, and a request reservation below the existing
8,000-token allowance. This is a bounded request-count test, not a hosted latency SLO.
Large groups still must fit the configured provider allowance: evidence is never
truncated and quota guards are never bypassed. Live confirmation of the fix is pending.
