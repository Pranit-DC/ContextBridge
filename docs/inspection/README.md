# ContextBridge V1 viewer

## Supported-provider onboarding (local UI complete; service integration pending)

The sidebar's **Provider setup** flow is available before the memory connection succeeds.
It supports only Groq `openai/gpt-oss-120b` and Cloudflare
`@cf/qwen/qwen3-embedding-0.6b`, with a 32-character hexadecimal Cloudflare account ID.
Load settings, choose **Keep current key**, **Use staged replacement**, or **Remove key**,
and explicitly confirm **Apply provider settings**. Loading and editing never change settings.
Revision conflicts preserve the draft and require reload/review. Replacement requires a key
staged privately by the shared service; the viewer never accepts or returns a provider key.

The default client deliberately reports **shared service settings integration pending**.
Automated tests inject a public-state settings substitute. There is no settings endpoint,
credential store, dotenv writer or provider fallback in this UI. Shared APIs/settings remain
Pranit's responsibility; [the integration request](integration-request.md#5-supported-provider-settings)
specifies what must be connected before this can configure a real installation.

Credential protection: only presence flags and fixed selection metadata cross the settings
boundary. Unknown response fields, invalid models and bypassed model validation are rejected.
Errors use fixed messages and discard exception context; raw HTTP bodies/errors are never
rendered or logged. No key value, suffix, fingerprint, screenshot, shared cache or report is
generated. Provider setup uses no password/key widget. The existing password widget is for the
distinct ContextBridge API token. Tests clear inherited viewer/provider credentials, prohibit
real HTTP transport, and use synthetic sentinels and temporary configuration files only.
No development check reads or changes an existing `.env` or installed agent configuration.
Private key staging/storage/validation and removal from running services still require the owner
implementation; UI tests do not establish those service-side guarantees.

**Validate saved settings offline** reports missing provider keys/account configuration without
reading a key or making requests. Unsupported providers/models and malformed account IDs are
rejected deterministically. It does not authenticate credentials or inspect provider billing.

**Run bounded online check** requires its own explicit consent and button press after the data
and quota disclosure. Its client request fixes two calls maximum, a 10-second overall deadline,
32 Groq output tokens, and a stop on the first failure, with no retries. Only `Reply OK.` and
`ContextBridge connectivity check.` may be sent, using saved settings, never memory/evidence/drafts.
Authentication, timeout, quota and unavailable outcomes have fixed labels. The owner must enforce
the transport deadline/call ceiling and account policy; this branch tests the UI/client boundary
with mocked transport, and does not implement or run a live settings-service check.

### Automated workflow coverage

Run `uv run --all-extras pytest tests/inspection` for widgets and mocked HTTP; run the full
README database suite separately to exercise the actual shared API and workers with synthetic
providers. Viewer tests block unmocked HTTP transport and never open a live model connection.

| Workflow | Automated evidence |
| --- | --- |
| First connection/setup | Missing/rejected token, invalid address, service recovery, pending real settings integration |
| Provider settings | Fixed model choices, malformed/missing configuration, confirmed replacement/removal, stale revision and draft recovery |
| Validation/check | Offline-only validation, explicit online consent, fixed request bounds, auth/timeouts, rejected unsafe reports |
| Save/import | Lost-response identity, malformed/failed imports, terminal processing states, no automatic replay |
| Search/browse/inspect | Empty and degraded results, project boundaries, pagination, literal evidence/history, no repeated hosted search on detail clicks |
| Correction | Stale writes, latest-version review, unsaved draft transfer, no automatic resubmission |
| Consolidation | Explicit queue/status requests, queued/running/succeeded/failed/deferred/cancelled states, no resubmit on rerun |
| Retire/restore/forget | Expected versions, fresh evidence, retirement conflicts, confirmed forgetting and draft cleanup |
| Service recovery | Save/import/correction drafts and stable request IDs survive a readiness outage |
| Accessibility subset | Visible nonempty widget labels, password masking, actionable text for invalid/destructive actions |

Save/import/correction/restore inputs now keep their editable state across reruns; only their
explicit action button mutates memory. Readiness outages temporarily hide controls without
discarding drafts. Connection changes and successful forgetting still clear private drafts.
These checks are **not a completed human accessibility review**. AppTest cannot establish browser
focus order, keyboard operation, contrast, zoom or screen-reader announcements. Those reviews,
Linux browser verification, Windows Docker Desktop walkthroughs and live-provider results remain
separate from these native Windows widget tests.
See the [Phase 3 verification record](phase3-verification.md) for exact results, earlier
intermittent Windows locking failures, skipped checks and pending owner integration.

The Streamlit viewer uses the shared HTTP API and has no database or model credentials of its own.
Start the API and optional workers with the V1 provider settings in
[V1 integration](../v1-integration.md), then run:

```text
uv sync --frozen --all-extras --python 3.12
uv run --extra viewer streamlit run src/contextbridge/inspection/app.py --server.address 127.0.0.1
```

Open `http://127.0.0.1:8501`. Enter the project, local API address and API token in the sidebar.
An environment `CONTEXTBRIDGE_API_TOKEN` can supply the token without sending its value to the
browser. Use `CONTEXTBRIDGE_PROJECT_ID` to choose the default project. Windows Docker Desktop
uses Linux containers and `127.0.0.1` for the published services.

## Controls

- **Browse:** paginated current memories in the selected project, or explicitly select memories
  shared across projects. Retired listing offers the same scope choice.
- **Search:** meaning, words and identifiers through the existing richer retrieval endpoint.
  Three cards by default; select more context for five. Condition and historical-time filters are
  explicit. Availability and evidence warnings stay visible. Search runs only when submitted;
  opening details does not repeat model calls. Results are not cached in server session state.
- **Save:** explicitly confirmed content, type, evidence, optional conditions and effective time.
  Choose this project or shared-across-projects scope. Background workers index authorized bindings;
  global indexing requires explicit developer-wide processing. Details show the actual indexing state.
- **Import:** a chosen JSON message list, explicit roles and a timestamp. Up to 20 messages and
  32,000 characters per event; no guessing roles or silent truncation. The online AI processes
  the import only for the configured capture project. Check progress explicitly. Deferred results
  remain pending; the viewer never turns an uncertain statement into an accepted fact.
- **Details:** evidence, version history, source metadata and indexing status. Generated summaries
  expose their original source versions and evidence, with buttons to inspect those memories.
- **Correct:** names the opened version and requires fresh evidence. Stale writes are rejected;
  the latest version is shown and the user's draft is preserved for review.
- **Maintenance:** submit one compatible batch of at most 20 current memories for consolidation,
  inspect its status, and browse retired memories. An unchanged source set is attempted once.
- **Retire / restore:** retirement stops current use and affected summaries while preserving
  history. Restoration requires the version and fresh user evidence and creates a new version.
  Generated summaries must be rebuilt from current sources.
- **Forget:** requires explicit confirmation. Permanently removes stored memory, history,
  evidence, vectors and related derived content/jobs. The viewer clears related drafts and IDs.

After a lost save/import response, retry the unchanged form: its request/event ID, timestamp and
source identity remain stable. A new or edited request needs the explicit new-request button.
Mutations are never retried automatically. Connection changes clear selection, job IDs and drafts.

## Boundaries and verification

The API token belongs to one configured developer and spans that developer's projects. The viewer
adds its selected-project boundary, rejects leaked or mismatched responses, and inspects IDs before
changes. Developer-wide memories can appear when explicitly included in retrieval. This is not a
multi-user login system.

Service content is rendered as literal text with control/direction characters removed. No Streamlit
cache, raw exception text or credential logging is used. The user's form drafts and selected IDs
remain only in the browser session. Readiness confirms service/schema configuration; it does not
claim an online provider was contacted. Missing indexing, provider failures and uncertain evidence
are visible. Verification reports support by stored evidence, not independent truth.

AppTest and HTTP-substitute tests cover controls, lost responses, scopes, stale writes, cleanup and
bounded search. PostgreSQL integration tests exercise the actual API, modules and workers with
synthetic providers through import/save, indexing/search, correction, consolidation, lifecycle and
forgetting. Live provider and host results are recorded separately in the final V1 report. A human
browser/accessibility review and the supplied Windows Docker Desktop check remain separate checks.
