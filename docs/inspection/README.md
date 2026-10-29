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
