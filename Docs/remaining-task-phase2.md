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

## Verification record

Final phase verification and remaining dependencies are recorded here before PR creation.
