# Candidate writes and paginated browse (contract V1, P2)

P2 executes admitted candidates through the shared PostgreSQL store. It supplies the
transaction boundary, persisted interpretations, version/relationship metadata, and the
agreed browse endpoint. Real Om/Harshal providers, background scheduling, vector indexing,
and actual integrated model-quality measurements remain pending.

## Injected processing

Call `WriteEngine(session, settings, modules).process(job_id)` with a configured
`ModuleGateway` containing an extractor and admission policy. This is a synchronous library
entry point for the later worker; it is not a new public processing endpoint and ingestion
does not execute it inline. Tests use recorded substitutes in Pranit-owned test directories.
There are no fake production providers. An empty extraction succeeds with no memory IDs;
unavailable/malformed providers produce safe, distinguishable job outcomes.

Extraction results are saved once per event, including an empty list, before admission.
Candidate identities are unique per configured developer and saved in original output order.
Admission decisions and write plans are then saved once per candidate. Retries use those
saved values; they cannot silently regenerate an interpretation. Transient provider failures
may retry. An uncertain interpretation/version conflict remains deferred and needs an explicit
future review/reprocessing flow or a new evidence-backed event; P2 exposes no reprocessing API.

Provider calls run outside mutation locks. Each commit rechecks owner/project binding,
raw/candidate expiry, supporting user/tool references, candidate identity/fingerprint,
conditions, target type/claim, and expected version. Comparison context contains current
records plus historical versions applicable at the candidate's effective time. Oversized
comparison contexts defer/fail safely instead of using a silently truncated decision context.

## Resolution and mutations

`SafeResolutionPolicy` handles exact duplicates and new claims without a model. It accepts
an optional `RelationInterpreter.compare(candidate, record)` for `same`, `correction`,
`contradiction`, `unrelated`, or `uncertain` proposals. The interpreter owns no storage.
Claim-label equality, confidence, and recency never establish contradiction or correction.
Without an interpreter, different meanings under the same conditions defer. Real semantic
interpretation remains pending; recorded test interpretations are not a quality result.

With formation enabled, comparison selection covers all classifications in the same authorized
scope and exact conditions, including missing or inconsistent claim labels. A related claim with
a different classification defers rather than guessing a type or silently creating clear competing
truth. Multiple contradictions also defer: contract V1 supports only one mutation target. Create,
update and conflict writes recheck the complete compared current-version set before mutation.

- New supported claim: create a version with evidence and claim/confidence metadata.
- Exact duplicate: return the existing result without another memory/version.
- Different conditions: preserve separate memories.
- Explicit supported correction: require `EXPLICIT_DECISION` in the plan, a current expected
  version, and a later effective time; append a version and `supersedes` edge atomically.
- Unjustified incompatible claims: preserve both versions, a `contradicts` edge, and
  `decision_state: contested`. This metadata is separate from ACTIVE/SUPERSEDED lifecycle status.
- Uncertain or backdated/out-of-order correction: defer; no silent overwrite.

Existing explicit API records retain null claim/confidence metadata and clear decision state
by default. Exact duplicates of legacy explicit records can be identified. Differently worded
legacy records without claim labels need later classification/retrieval integration before
automatic relationship resolution; explicit correction remains available through the existing API.

Version-only derivation edges can be staged through `add_derivation` after live, owner,
project, and exact-conditions checks. Consolidation proposal validation/commit is still P4 work.

## Retention and forgetting

`CONTEXTBRIDGE_CANDIDATE_RETENTION_SECONDS` defaults to 3,600; range 60–2,592,000 seconds,
capped by the parent event expiry. Rejected candidates immediately discard payload/fingerprint.
Deferred/pending candidate expiry cancels its job and erases its raw event and cached content.
Applied candidates lose their content copies at expiry but keep IDs needed for provenance.
The existing expiry command covers both raw events and candidates. Operational sweep intervals
and backup/WAL limitations remain as documented in [ingestion](ingestion.md).

Forget clears associated raw events and all cached candidates/admissions/plans, leaving safe
ID/status cancellation markers. Cached or in-flight target corrections cannot recreate a forgotten
memory. Scoped transitive `derived_from` records are also deleted, with a conservative 200-memory
closure bound: larger deletion requests fail before mutation. [P3](retrieval-persistence.md)
adds vector/reindex cleanup. P4 will extend it to caches, consolidation, queue/outbox work,
and worker recovery.

## Browse API for the viewer

Authenticated `POST /v1/inspection/browse` takes `BrowseQuery` and returns `BrowseResult`:
[query example](team-plan/fixtures/browse-query.json),
[result example](team-plan/fixtures/browse-result.json).
The service supplies owner identity. Explicit scope/project, all stored conditions, and
`[valid_from, valid_to)` filters apply before the result limit. Developer scope is selected
explicitly; project browsing does not automatically include global records.

Limit defaults to 20, maximum 100. Items preserve nested MemoryResponse/version/evidence and
add claim_key, confidence, and decision_state. Existing memory/MCP response shapes are unchanged.
The opaque signed cursor holds only pagination IDs/time and a binding hash. It binds owner,
scope/project, conditions, and requested as_of; tampering or reuse with different filters is 422
INVALID_INPUT. The resolved time stays fixed across pages. Sorting is deterministic by memory UUID;
concurrent additions/deletions can still alter available rows, so this is not a database snapshot.
Token rotation invalidates existing cursors. Safe new-endpoint errors retain `{detail:{code,retryable}}`.
