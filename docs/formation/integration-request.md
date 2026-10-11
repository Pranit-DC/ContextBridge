# Formation integration requests for Pranit

Contract version: 1. No common-contract change or new dependency requested for O1.

## Wiring requested

- Inject `formation.Extractor` and the initial `formation.AdmissionPolicy` through the shared
  engine. Keep `extract(event)` and `assess(candidate, ComparisonContext)` dictionary boundaries.
- Supply an authorized event reader to admission's `event_lookup(event_id)`. It must enforce
  configured developer/project binding and retention. Missing/expired/deleted evidence must not
  become successful admission. The module has no separate memory store.
- Supply fresh ComparisonContext records and recheck scope, source/evidence, effective time,
  expected versions and cancellation/deletion state immediately before committing. Admission
  does not resolve conflicts, write versions, or prevent a race with forgetting by itself.
- Reuse P2's saved extraction results and stable candidate IDs once per event.
  Provider determinism is not an exactly-once guarantee; do not silently reinterpret retries.
- Unsupported/uncertain extraction output raises safe `INVALID_PROVIDER_OUTPUT`; distinguish it
  from a successfully empty `[]` result. Provider timeout/connection failure raises retryable
  `PROVIDER_UNAVAILABLE`. Admission maps unavailable verification to DEFER/PROVIDER_UNAVAILABLE.
  Invalid event/candidate/context input raises `INVALID_INPUT`; no raw exception text is returned.

## Provider decision pending

The team must select a model provider and a semantic evidence verifier for budget, privacy,
language and hardware before O3. No network calls, paid provider selection, or private-data
submission is introduced here. Pranit owns any new shared configuration, timeout setting,
dependency or lockfile change. Proposed provider interfaces are local formation internals, not
changes to common contracts. Real implementations must bound calls and check semantic support,
atomicity, conditions, scope, dates and adoption, rather than trust excerpt matching or confidence.

## Checks that remain pending

- Production event-lookup/provider wiring, workers, and real-provider retry/failure checks.
- Real model extraction/verification, fixed unseen examples, quality baseline and agreed targets.
- Consolidation proposals, source-version freshness and forgetting during processing (O4).

## Recorded P2 integration

The native Windows/PostgreSQL 18 full suite passed with zero skips on 11 October 2026, including
formation-to-P2 writes, repeat processing, admission rejection/deferral, and forgetting cleanup.
The test providers and evidence labels were recorded fixtures. These tests do not establish
production provider wiring, semantic model quality, or worker/consolidation behavior.

The O1 unit suite and sample runner use recorded synthetic fixtures. Their passing results show
contract/error/policy behavior only, not semantic model quality or a functioning end-to-end worker.
