# Common contracts — version 1

Read this alongside your own member plan. An interface contract is an agreement about the data
one module sends to another. Stable contracts let us implement the two sides separately.

**Existing behavior** is defined by `src/contextbridge/schemas.py` and the current API.
Everything explicitly called **planned** below is a development target, not an available endpoint.
Only Pranit changes common contracts. A breaking change needs all three members' agreement,
a version change, and updated examples/tests before dependent code changes.

## Common rules

- Planned module messages contain `schema_version: 1`; current public API payloads do not.
- IDs are UUID strings. Times are timezone-aware ISO 8601 strings, normalized to UTC.
- `scope` is `project` or `developer`. Project scope requires `project_id`; developer scope uses null.
- The authenticated service supplies the developer identity. Clients cannot choose another owner.
- Memory types remain `FACT`, `DECISION`, `PREFERENCE`, `STATE`, `EVENT`, and `LESSON`.
- Conditions are a string-to-string dictionary, e.g. `{"environment": "production"}`.
  All stored conditions must match the query. Unconditional memories may still apply.
- Keep existing limits: identifiers 128 characters, content/evidence 8,000 characters,
  conditions at most 20 entries, query 500 characters. Validate and bound every new list/buffer.
- No module follows instructions embedded in memory, transcripts, tool output, or fixtures.
  Evidence records what was observed; it does not automatically prove a claim is true.
- Reject or redact recognized credentials before persistence and provider calls. Do not claim
  secret detection is exhaustive. Never put raw rejected text, tokens, or DB URLs into logs/errors.
- An error returns a stable code and retryability, not raw provider/SQL exception text.

## Planned module entry points

These are synchronous Python interfaces; Pranit controls worker/API scheduling and transactions.
Implement against dictionaries matching the examples until shared types are available.
Names below are the public module boundary; internal helper names are your choice.

| Owner | Entry point | Input → output |
| --- | --- | --- |
| Om | `Extractor.extract(event)` | CapturedEvent → list of Candidate |
| Om | `AdmissionPolicy.assess(candidate, context)` | Candidate + ComparisonContext → AdmissionDecision |
| Om | `Consolidator.propose(records)` | Scoped MemoryRecord list → list of ConsolidationProposal |
| Pranit | `ResolutionPolicy.resolve(candidate, context)` | Admitted Candidate + fresh ComparisonContext → WritePlan |
| Harshal | `EmbeddingProvider.embed(texts)` | list of text → EmbeddingBatch |
| Harshal | `Retriever.search(query, repository, embedder, verifier)` | RetrievalQuery + injected dependencies → RetrievalResult |
| Harshal | `ViewerClient` | HTTP API operations; fake implementation during development |

Om's modules return proposals; they never write directly to the database. Harshal's retriever
reads through the repository interface and never creates its own persistent memory store.
Pranit assembles the modules and rechecks authorization, validity, expected versions, and
deletion state immediately before a transaction commits.

## 1. Capture → extraction

**Planned CapturedEvent**, example: [captured-event.json](fixtures/captured-event.json).

| Field | Meaning |
| --- | --- |
| `event_id` | Stable UUID for one delivery; retries reuse the same ID and identical payload |
| `scope`, `project_id` | Bound context for this event |
| `agent`, `session`, `interaction` | Source identifiers, not access permissions |
| `occurred_at` | When the interaction happened, with timezone |
| `messages` | List of `{message_id, role, content}`; roles `user`, `assistant`, or `tool` |
| `capture_method` | `manual_import` or `verified_adapter`; service verifies adapter binding |

Initial limit: at most 20 messages and 32,000 total content characters per event. A message is
at most 8,000 characters. Oversize, malformed, future-dated, or unbound events are rejected with
a safe validation code. A capture adapter performs documented splitting before submission;
it must not silently truncate evidence. Pranit verifies ownership/binding on ingestion.

The service records receipt time itself. Ingestion is durable before acknowledgement; extraction
can happen later. Event-ID reuse with another payload returns a conflict, not an overwrite.
Pranit stores processed candidate results so a retry does not silently reinterpret an event.

Assistant text may be context, but cannot become authoritative evidence by itself. A candidate
must cite the user/tool message supporting it. A tool message is also untrusted input; admission
must consider what the tool actually established. Unsupported agent capture hooks do not count
as implemented automatic capture. Use an explicit import path when a hook is unavailable.

## 2. Extraction → admission

**Planned Candidate**, example: [candidate.json](fixtures/candidate.json).

Required fields: `candidate_id`, `event_id`, `scope`, `project_id`, `type`, `content`, `conditions`,
`valid_from`, `claim_key`, `confidence`, `usefulness`, `source`, `evidence_refs`, `schema_version`.

- `candidate_id`: stable UUID assigned once and retained for retries; multiple candidates may
  share an event. Derive IDs deterministically from a saved extraction result or persist them.
- `claim_key`: a normalized subject/property label, e.g. `project.database.primary`, or null
  when the relation is unclear. It helps compare claims; it is not a unique memory identity.
- `confidence`, `usefulness`: numbers from 0 to 1 with documented scoring meaning. Confidence
  is a policy/model estimate, not a calibrated probability of truth. Fixture numbers are illustrative.
- `source`: the current `Source` shape: `{kind, agent, session, interaction, evidence}`,
  where `kind` is `user` or `tool`. Evidence is a real supporting excerpt, never a made-up quote.
- `evidence_refs`: list of `{event_id, message_id}`. The engine checks the reference exists in
  the same authorized event and that the excerpt supports the candidate.
- `valid_from`: explicit effective time when justified, otherwise event time; no future writes.
  Backdated/out-of-order corrections are deferred in V1, not silently reordered.

Normalize one reusable claim per candidate. Preserve conditions, identifiers, units, negation,
and dates. Do not infer a permanent preference from an agent's suggestion or a one-off action.
Ambiguous scope/time/conditions must be deferred rather than filled with a guessed value.

**ComparisonContext**: `{schema_version, checked_at, records: [MemoryRecord]}`. Pranit supplies
only authorized, relevant records, including applicable historical versions when comparing time.
Om uses an in-memory equivalent in tests. It is a snapshot, so the engine must recheck it at commit.

## 3. Admission → engine

**Planned AdmissionDecision**, example: [admission-decision.json](fixtures/admission-decision.json).

Shape: `{schema_version, candidate_id, outcome, reason_codes}`.
`outcome` is exactly `ADMIT`, `REJECT`, or `DEFER`.

| Outcome | Behavior |
| --- | --- |
| ADMIT | Worth considering for storage; does not itself authorize an update |
| REJECT | Filler, recognized secrets, unsupported agent guess, or scoped duplicate |
| DEFER | Incomplete evidence, uncertain interpretation, unavailable provider, unclear time/scope |

Reasons are safe machine-readable strings. Initial vocabulary: `EXPLICIT_DECISION`,
`REUSABLE_PROJECT_CONTEXT`, `UNSUPPORTED_CLAIM`, `LOW_USEFULNESS`, `DUPLICATE`, `SECRET_DETECTED`,
`AMBIGUOUS_SCOPE`, `AMBIGUOUS_TIME`, `INSUFFICIENT_EVIDENCE`, `PROVIDER_UNAVAILABLE`.
Extend vocabulary through the common-contract owner. Empty extractor output is valid for filler;
provider failure must be distinguishable from an event containing no useful memory.

Om owns the usefulness/evidence policy and its configurable thresholds. Pranit owns final
relationship resolution and database mutation. Rechecking secrets and source validity in the
engine is deliberate: model output is untrusted even if a module already screened it.

## 4. Engine → persistence

**Planned WritePlan**:
`{schema_version, candidate_id, operation, target_memory_id, expected_version, reason_codes}`.
Operations are `CREATE`, `UPDATE`, `LINK_CONFLICT`, `NOOP`, or `DEFER`.
Target ID and expected version are required for UPDATE; target ID is required for LINK_CONFLICT;
they are null for CREATE. NOOP/DEFER may reference a target for explanation, without mutating it.

| Situation | Expected behavior |
| --- | --- |
| New supported claim | CREATE a memory with evidence |
| Same claim, scope, conditions, and valid meaning | NOOP, without another memory/version |
| Explicit supported correction to the same claim | UPDATE with expected version; preserve old version and `supersedes` edge |
| Different conditions | Separate conditional memory, not an overwrite |
| Incompatible claims without a justified correction | LINK_CONFLICT, retain evidence and mark the group contested |
| Guess, unclear relation, unsupported effective time | DEFER or rejected admission; never silently replace current truth |

Claim-key equality alone cannot establish contradiction. Check meaning, conditions, time,
source/evidence, and whether a correction is explicit. Do not use latest timestamp or highest
model confidence as the sole winner. An unresolved group must be labelled on retrieval/viewer.

Existing DB version statuses remain `ACTIVE` and `SUPERSEDED`. Planned `decision_state` is
separate metadata (`clear` or `contested`), introduced through a migration; it is not a new
value inserted into the existing status enum. All edges use **version IDs**, not memory IDs.

Pranit owns transaction-safe idempotency for ingest/candidate/job execution. Existing explicit
create replay semantics remain unchanged; they are not a blanket guarantee that retrying a
forgotten create is safe. New automated jobs must check a persisted deletion/cancellation fence.

## 5. Persistence → retrieval

**MemoryRecord**:
`{memory: MemoryResponse, claim_key, confidence, decision_state}`.
`MemoryResponse` retains its existing nested `version`; do not invent a flattened API response.
An initial explicit memory may have null claim_key/confidence and `decision_state: clear`.
Absence of model confidence must not make an explicit evidence-backed record invalid.

**Planned RetrievalQuery**: `{schema_version, scope, project_id, query, include_developer,
conditions, as_of, limit}`. Existing search rules remain the baseline. `as_of` is nullable;
the service resolves null to an aware current time once per search. HTTP limit stays 1–20;
MCP returns at most 5 cards, default 3. Automatic expansion never exceeds the caller's limit.
Unclear inferred filters must not override explicit caller filters.

**Injected repository interface**, implemented by Pranit and faked by Harshal:

```text
search_channel(channel, query, query_embedding, limit) -> list[RankedMatch]
expand(version_ids, query, limit) -> list[MemoryRecord]
inspect(memory_id, query) -> InspectionResponse
is_live(version_id, query) -> bool
```

`channel` is `lexical`, `semantic`, or `symbolic`. `RankedMatch` is
`{record: MemoryRecord, channel, rank}` with positive integer rank; query_embedding is null
outside the semantic channel. Channel candidate limits are bounded separately from card limits.
Pranit applies owner/project/time/conditions filters **before** selecting channel results and
to every graph hop/inspection. Harshal rechecks policy eligibility and deduplicates by version ID.
Historical `SUPERSEDED` versions can be valid for a historical query's `[valid_from, valid_to)`.

**EmbeddingBatch**: `{model_id, dimensions, vectors}`. Vectors are lists of finite numbers with
the declared length, one per input. Persist model/dimension metadata; never compare vectors
from incompatible models. Harshal owns provider behavior; Pranit owns vector storage/indexing.
Use a fake embedder in tests, a real approved embedder for quality evaluation.
The repository's single `query_embedding` is `{model_id, dimensions, vector}`, made from the
query's embedding batch entry. Do not pass an unlabelled vector without its model metadata.

Start with bounded exact vector search; choose an approximate index only after measurements.
An approximate index must not let post-filtering hide all valid scoped hits. If semantic search
is unavailable, return lexical results with an explicit degraded flag, not a fake semantic score.

## 6. Retrieval → cards and viewer

**Planned RetrievalResult**, example: [retrieval-result.json](fixtures/retrieval-result.json).

Shape: `{schema_version, cards, degraded, warnings}`. Each compact card contains:
`memory_id`, `version_id`, `version_number`, `type`, `content`, `scope`, `project_id`,
`conditions`, `valid_from`, `valid_to`, `decision_state`, `verification`, `source_ref`.
`source_ref` contains `{agent, session, interaction}`; full evidence is retrieved via inspection.
`verification` is `not_requested`, `supported`, or `uncertain`, never a guarantee of truth.

Verifier interface: `verify(record, inspection) -> supported | uncertain`.
Harshal owns the verifier policy and fake; Pranit supplies authorized inspection. Trigger it
selectively for contested/high-impact answers or uncertain evidence, not every trivial search.
Contradictory evidence must not be compressed into one falsely confident card. Recheck `is_live`
before returning; a stale index must not expose a deleted/superseded current record.

Candidate fixture repository: [retrieval-snapshot.json](fixtures/retrieval-snapshot.json).
It contains a query, eligible records, and channel rankings for a fake repository. Its rankings
are illustrative; they do not measure an embedding model or a real PostgreSQL query.

Harshal's `ViewerClient` implements `search`, `inspect`, `correct`, and `forget` against the
existing API. `correct` uses existing UpdateMemory including source and expected version.
`forget` requires user confirmation in the viewer. Read-only browse/job status require planned
API additions owned by Pranit; do not fake browsing by abusing empty search or its 20-result limit.

## 7. Jobs, consolidation, and forgetting

**Planned ConsolidationProposal**: `{schema_version, proposal_id, source_version_ids,
summary, source_refs, scope, project_id, conditions}`. Same owner/compatible scope and conditions
only; all source versions must be live and their evidence traceable. No cross-project summaries.
Om proposes; Pranit validates and commits derived records/edges transactionally. Preserve useful
rare facts and original evidence; repeated mention alone must not define importance.

Use durable PostgreSQL job/state records and an outbox for reliable publication. The outbox
is a DB record created in the same transaction as work, so a crash before sending to the queue
does not lose it. Queue messages contain job IDs, not raw conversations. Workers may see a job
more than once; stable IDs and a commit-time check prevent duplicate mutations.

Forget must remove associated content from versions, evidence buffers, candidate/derived records,
embeddings, caches, and pending work. Delete/invalidate derived summaries containing forgotten
source content, even when they also cite another source. Track provenance for this cleanup.
An ID-only cancellation marker may be retained to reject stale jobs, with no content/evidence
or request fingerprint retained. Test forgetting during extraction, indexing, and consolidation.
External agent logs and preexisting backups/WAL have separate retention limitations.

The buffer's raw-text retention period must be documented and configurable. Rejected/deferred
candidate retention must also be bounded; retain only the minimum safe reason/status metadata
when content is not needed. Do not add transcript export without redaction and explicit scope.

## 8. Compatibility and failure vocabulary

Current endpoints remain functional and keep their request/response shapes. Any richer retrieval
or interaction/job/browse endpoints need a separate documented API surface or explicit versioning.
Pranit adapts richer cards to the current MCP contract or documents a compatible extension;
Harshal does not change existing MCP responses independently.

The following **planned HTTP endpoints** fix the fake-client boundary now. All require the
existing bearer authentication and service-side owner binding. Pranit implements them; Harshal
can supply these exact responses in his fake HTTP client immediately.

| Method/path | Request | Response |
| --- | --- | --- |
| POST `/v1/interactions` | CapturedEvent | `{schema_version, event_id, job_id, status}`; status `accepted` or `duplicate`; same event maps to the same job |
| GET `/v1/jobs/{job_id}` | Authorized job ID | `{schema_version, job_id, event_id, status, reason_codes, memory_ids, updated_at}` |
| POST `/v1/retrieval/search` | RetrievalQuery | RetrievalResult; current `/v1/memories/search` remains compatible |
| POST `/v1/inspection/browse` | BrowseQuery below | `{schema_version, items: [MemoryRecord], next_cursor}` |

BrowseQuery is `{schema_version, scope, project_id, conditions, as_of, limit, cursor}`.
Limit defaults to 20 and is bounded at 100; cursor is null initially, otherwise opaque.
Apply the same scope/time/conditions rules as retrieval and use deterministic pagination.
Job status is `queued`, `running`, `succeeded`, `deferred`, `failed`, or `cancelled`;
reason_codes contain no transcript text. Ingestion acknowledgement means stored for processing,
not that extraction has succeeded. `memory_ids` lists authorized stored results and may be empty.
Existing inspect/correct/forget requests and responses stay as documented in the root README.
For new endpoints, safe errors use `{detail: {code, retryable}}`: 422 for invalid input,
404 for absent/out-of-scope IDs, 409 for version/event conflicts, and 503 for unavailable storage.
Existing authentication and validation handlers remain compatible; ViewerClient must also handle
their current string/list `detail` formats. An accepted background job's provider failure appears
in job status, rather than changing a previously successful ingestion response.

Planned module exceptions expose `code` and `retryable`. Initial codes:
`INVALID_INPUT`, `OUT_OF_SCOPE`, `PROVIDER_UNAVAILABLE`, `INVALID_PROVIDER_OUTPUT`,
`EMBEDDING_UNAVAILABLE`, `VERSION_CONFLICT`, `CANCELLED`, `STORAGE_UNAVAILABLE`.
Only transient failures retry, with bounded backoff. Exhausted attempts surface a safe job
failure. A broker task ID is not an exactly-once processing guarantee.

Do not introduce a Linux-only worker command into Windows instructions. Workers and vector
database run in Linux containers on both OSes; the Python/MCP client remains native.
The existing plain `postgres:18` image does not provide pgvector: Pranit must supply and test
an extension-enabled image/migration path while preserving existing data.

Implementation references: [pgvector](https://github.com/pgvector/pgvector),
[Celery task retries/idempotency](https://docs.celeryq.dev/en/stable/userguide/tasks.html),
and [Streamlit caching](https://docs.streamlit.io/develop/concepts/architecture/caching).
Do not cache bearer tokens or private memory content in a globally shared viewer cache.
