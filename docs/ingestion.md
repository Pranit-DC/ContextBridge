# Durable interaction ingestion (contract V1, P1)

The ingestion API stores an interaction and a queued job in one PostgreSQL transaction.
A 202 acknowledgement means the event is durable. Ingestion leaves it queued; the
[P2 write engine](write-engine.md) can process it through explicitly injected providers.
Background scheduling and real formation/retrieval integration remain pending.
Existing explicit memory and MCP requests keep their current shapes and behavior.

## Binding and authentication

Both endpoints require the existing bearer token. Set `CONTEXTBRIDGE_CAPTURE_PROJECT_ID`
to the project this API instance may ingest and inspect jobs for. Without a binding, ingestion
and job status are disabled (503 `PROVIDER_UNAVAILABLE`). The service supplies the developer
identity; neither a payload nor source metadata can override it. Different project bindings
may use the same database. As with the existing API, this is a single-developer service,
not per-project credentials or multi-user authorization.

Developer-scope events require the explicit setting `CONTEXTBRIDGE_CAPTURE_ALLOW_DEVELOPER=true`.
Project events must match the configured project exactly. Jobs outside the configured owner
and permitted scope return 404, including requests with a valid but unrelated job UUID.
Only `manual_import` capture is enabled in P1. `verified_adapter` is a reserved contract value
and is rejected until a real adapter binding is implemented; a caller's agent name proves nothing.

## HTTP operations

`POST /v1/interactions` takes the version-1 `CapturedEvent` in
`docs/team-plan/fixtures/captured-event.json`. It returns HTTP 202:

```json
{"schema_version":1,"event_id":"11111111-1111-4111-8111-111111111111","job_id":"55555555-5555-4555-8555-555555555555","status":"accepted"}
```

An identical normalized event replay returns the original job and `status: "duplicate"`.
A changed payload with the same event ID returns 409 `VERSION_CONFLICT`. IDs are isolated
by service owner. A retry cannot renew the retention deadline. Use the original stable event ID
on retries; never create a new ID merely because an acknowledgement was lost.

`GET /v1/jobs/{job_id}` returns:

```json
{"schema_version":1,"job_id":"55555555-5555-4555-8555-555555555555","event_id":"11111111-1111-4111-8111-111111111111","status":"queued","reason_codes":[],"memory_ids":[],"updated_at":"2026-10-11T10:00:00Z"}
```

P1 produces `queued` and retention-expired `cancelled` jobs, with no resulting memory IDs.
P2 processing also produces `running`, `succeeded`, `deferred`, and `failed`, with safe reasons
and authorized result IDs. Status never exposes raw messages.
New endpoint errors use `{"detail":{"code":"INVALID_INPUT","retryable":false}}`.
Validation is 422; absent/out-of-scope IDs are 404; replay conflicts and cancelled replays are
409; storage/configuration/capacity unavailability is 503. Storage failures and buffer capacity
are retryable; missing configuration and cancelled events require operator/user action.
The existing authentication errors retain their current format.

## Bounds and retention

Events have 1–20 messages, at most 8,000 characters per message and 32,000 total content
characters. Message IDs must be unique. Timestamps must be aware and not future-dated.
Common credential patterns are screened in every decoded field before persistence or module
calls. This is not an exhaustive detector. The new endpoints also bound HTTP body size at
512 KiB before JSON parsing, including requests without Content-Length. This accommodates
JSON-escaped Unicode within the character limits.

`CONTEXTBRIDGE_CAPTURE_RETENTION_SECONDS` defaults to 86,400 (one day; range 60–2,592,000).
`CONTEXTBRIDGE_CAPTURE_MAX_BUFFERED_EVENTS` defaults to 1,000 per configured developer across
projects (range 1–100,000). Concurrent requests cannot exceed that content-bearing row cap.
Capacity rejection uses retryable `STORAGE_UNAVAILABLE`; retrying an accepted event remains
possible when full. These limits do not silently truncate messages or discard accepted work.

Expiry clears the entire saved event payload and fingerprint, cancels queued work, and retains
only IDs, owner/scope, times, and safe cancellation status. The retained identity prevents a late
replay from restoring expired text: it returns 409 `CANCELLED`. Metadata-only markers are not
automatically pruned. PostgreSQL backups/WAL and external transcripts have separate retention.

Expiry runs on ingestion and job-status access for the configured binding. For idle services,
run `uv run contextbridge-expire-capture` regularly (for example every minute) with the same
settings. One run covers the configured project and opted-in developer scope. Run it for each
binding if several projects share the database. Expiry is transactional and safe to repeat.
Physical removal occurs at the next sweep/access, so operational retention includes that sweep
interval and downtime. The P4 worker scheduler will automate this maintenance.

## Module boundary

`contextbridge.contracts` exports version-1 validation models and synchronous protocols.
Collections are bounded: 100 extracted candidates/result memory IDs, 200 comparison or
consolidation records, 200 embedding vectors with 1–4,096 finite dimensions, 20 reason/warning
codes, and 2,048 characters per browse cursor. These are resource bounds for V1 adapters;
candidate limits and embedding dimensions remain separate from the 1–20 HTTP card limit.
`contextbridge.engine.modules.ModuleGateway` accepts explicit extractor/admission/resolution/retriever instances,
validates their output, and maps unexpected failures to safe module errors. It has no fake
production defaults and owns no database or background scheduling. Tests inject fixture-based
substitutes. P2 persists extraction results and executes write plans through `WriteEngine`;
calling the gateway alone neither acknowledges nor completes an ingestion job. Candidate
retention, replay, and capture-aware forgetting are documented in [write engine](write-engine.md).
