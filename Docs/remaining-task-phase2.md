# Remaining tasks Phase 2

Branch starts at merged `origin/develop` (`a44be81`); no earlier phase branch is imported.
Core engine/persistence/runtime additions use the 13 October integration exception in
`team-plan/README.md`. Formation, retrieval and inspection owned implementations and their
tests remain untouched. Contract V1 message shapes are unchanged.

## Bounded session grouping

Explicit imports remain the only capture source. Set `CONTEXTBRIDGE_CAPTURE_GROUPING_ENABLED=true`
on the worker to opt in to batching accepted captures. No host hooks are installed.
Related here means identical authorized owner/scope/project, agent and session, rather than
an inferred semantic relationship. Receipt order is stable; event message order is preserved.
Delayed imports retain their own source timestamps and identities.

Defaults: 30 idle seconds, 5 events, 20 messages, 32,000 content characters. Configure with
`CAPTURE_GROUP_IDLE_SECONDS`, `CAPTURE_GROUP_MAX_EVENTS`, `CAPTURE_GROUP_MAX_MESSAGES`,
`CAPTURE_GROUP_MAX_CHARACTERS` (each prefixed `CONTEXTBRIDGE_`). Limits cannot exceed V1
event bounds. A single previously accepted event exceeding a smaller configured soft bound
is processed alone. Overflow seals the earlier group. A `ReadinessPolicy` can be injected
into `WorkRunner` for deterministic scheduling tests. Idle is measured from service receipt,
never the possibly old source occurrence time. Actual readiness is checked at worker delivery;
scheduler/broker cadence can add delay. Partial groups consume no execution attempts.

Migration `a25f0138ce41` adds only a nullable, indexed job-to-leader UUID foreign key. It
copies no content and leaves old jobs independent. Frozen membership survives restart and
configuration changes. The owner lock serializes assignment and leases. New arrivals after
freezing go to a later group. A crash between member commits resumes saved interpretations;
already applied candidates remain idempotent. Original event/job acknowledgement and replay
identities do not change. Existing raw capacity, expiry and cancellation rules still apply;
forgetting any frozen group's source cancels/erases its whole shared context.

Extraction receives a bounded synthetic V1 event with reversible message aliases. Before
persistence, candidates recover original event/message IDs, source agent/session/interaction
and default occurrence times. Original evidence is validated again. A proposal citing several
events is deferred: V1 evidence/admission cannot represent that proposal safely. This is an
explicit integration limitation, not permission to silently extend the common contract.

Deterministic comparison: three accepted single-message events require three per-message
extractor calls, versus one grouped call (67% fewer), with all three original source bindings
preserved. Admission/relation/provider audits can still require calls per candidate; these
tests count injected extraction calls, not actual hosted request costs or semantic accuracy.
Tests use real PostgreSQL and worker leases, with injected extraction/admission substitutes.
Live hosted batching quality and provider cost remain pending independent evaluation.

## Relative-time normalization

`engine/relative_time.py` is a deterministic source-context policy around the existing formation
boundary. It recognizes today/yesterday/yday, numeric or one/a days/weeks ago, and the previous
calendar week. Only an explicit clock and a justified source timezone can produce an instant.
Date-only input produces a date; week input produces an exclusive-end calendar date range.
No receipt time, current wall-clock time, units conversion or meaning rewrite is used.
Negation, units, identifiers and the verbatim evidence remain unchanged. Uncertain wording,
multiple time references, unsupported relative expressions, missing context, and DST gaps/folds
defer safely. This is a bounded vocabulary, not general natural-language temporal interpretation.

The source timezone must be explicitly bound with `CONTEXTBRIDGE_CAPTURE_SOURCE_TIMEZONE`
(IANA name, for example `Asia/Kolkata`). It is the timezone of the imported source, not the
worker or importing computer. Leave it unset for mixed/unknown source zones. V1 timestamp
validation normalizes offsets to UTC, so the engine cannot reconstruct the original local
calendar timezone from a delayed import. Per-source timezone metadata is a future contract task.

Example: source `2026-10-15T00:15:00+05:30`, timezone `Asia/Kolkata`, statement
"We switched to SQLite yesterday." normalizes to "We switched to SQLite 2026-10-14."
Precision is **date**, with **no exact instant**. With `America/Los_Angeles`, that same source
instant refers to 13 October as yesterday. Delaying import does not change either result.

The integrated V1 write engine returns `deferred / AMBIGUOUS_TIME` for this date-only claim.
It does not store a fabricated effective timestamp. Date/range storage and precise backdated
correction semantics require an agreed contract extension and remain pending. Exact relative
times such as "yesterday at 09:30" can pass to existing evidence/admission/resolution checks.
This preserves common V1 and leaves Om's semantic normalization implementation untouched.

## Query understanding

The shared retrieval boundary identifies bounded database/runtime/cache/API topic aliases and
current-state/historical intent. It preserves the original query and all explicit scope, project,
condition and time filters. No query rewriting, expansion or inferred authorization is introduced.
It returns empty V1 cards with safe clarification warning codes when a version label (such as V1)
lacks an explicit `conditions.version`, wording conflicts with that filter, historical wording
has no explicit `as_of`, a named project differs from the binding, or a short topic is ambiguous.
Clarification runs before any retrieval/provider call. Original keyword API behavior is unchanged.

References can resolve only to one topic in an explicitly injected `AuthorizedQueryContext`
matching owner, scope and project. No global conversation cache is added. The public V1 query
has no session binding; actual host/session reference-context integration remains pending.
Unbound/ambiguous references defer. Topic/intent annotations are deterministic heuristics, not
general language understanding; they do not claim improved semantic recall or change channel text.

## Conflict-aware reranking

After existing fusion/verification, the shared service validates exact stored cards again under
the owner lock. It requests a pool of the requested limit plus four, capped at 20, then reads
at most 200 contradiction edges whose **both endpoints** satisfy the same owner/project,
condition and effective-time eligibility. Inapplicable historical/conditional/private endpoints
cannot influence rankings or even conflict warnings. Existing fusion remains unchanged.

An injectable `ConflictRankingPolicy` prefers clear context only within relevance windows of
four, preserving project precedence. Connected eligible alternatives stay adjacent when possible;
contested/edge-linked cards are always labelled uncertain, regardless of verification or model
confidence. Ranking does not choose a winning claim. Cardinality limits still hold and omitted
alternatives, absent pool counterparts and edge-bound saturation receive warning codes. Full
inspection remains the route to all authorized evidence and history. A fixed pool cannot promise
to retrieve every conflict counterpart in a larger store; warnings make that limitation visible.

Deterministic regressions compare unchanged fusion with the policy: clear database context can
move before two contested alternatives, both alternatives survive a sufficient card limit, and a
one-card limit explicitly marks omission. Highly similar stale and wrong-condition records remain
ineligible; historical queries still use the applicable older version. No semantic-quality or
live-provider relevance improvement is inferred from these policy regressions.

## Verification record

Final phase verification and remaining dependencies are recorded here before PR creation.
