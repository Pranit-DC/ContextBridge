# Integration requests to Pranit (viewer)

Nothing here has been changed outside `src/contextbridge/inspection/`, `tests/inspection/`,
`scripts/inspection/`, and `docs/inspection/`.

## 1. Streamlit dependency and launch entry point

The viewer imports `streamlit`, which is not in `pyproject.toml` or `uv.lock`. Please add it as an
**optional** group so the service and MCP adapter stay light, for example:

```toml
[project.optional-dependencies]
viewer = ["streamlit>=1.40,<2"]
```

and, if you want a launcher, a script such as `contextbridge-viewer` that runs
`streamlit run` on `contextbridge/inspection/app.py`. The app was tested with Streamlit 1.65.0.
Until then it runs with `uv run --with streamlit streamlit run src/contextbridge/inspection/app.py`,
and `tests/inspection/test_app.py` skips itself when Streamlit is not installed. Once the group
exists, CI could install it so those 15 screen tests run there too.

## 2. Windows: use 127.0.0.1 for the database, not localhost

On Windows with Docker Desktop, `localhost` resolves to IPv6 first while Compose publishes the
database only on `127.0.0.1`. Every connection then waits about 8 seconds before falling back.
Observed here: the API timed out on its first write, and the full test suite appeared to hang at a
PostgreSQL test. With `127.0.0.1` the same viewer check ran in 5 seconds. These shared files use
`localhost`:

- `.env.example` (line 6)
- `scripts/setup_local.py` (the `.env` it generates)
- `docs/windows-setup.md` and the `README.md` test-database example

Suggested: write `127.0.0.1` in those, or publish the port on `::1` as well. I worked around it
locally with an environment override and did not edit any `.env`.

## 3. What the viewer relies on (already implemented)

- `POST /v1/inspection/browse` with the contract's BrowseQuery and BrowseResult, project scope
  excluding developer-global records, and cursor errors returned as 422.
- `GET/PUT/DELETE /v1/memories/{id}`, `POST /v1/memories/search`, and `GET /health/ready` as today.
  The viewer treats `409` on `PUT` as a stale version.

## 4. Later

When `POST /v1/retrieval/search` exists, the viewer could show retrieval cards, including the
`verification` label and any "related memory" disclosure. That needs the card marker described in
[docs/retrieval/integration-request.md](../retrieval/integration-request.md).

## 5. Supported-provider settings

Phase 3 adds a viewer-local `SettingsClient` protocol in `inspection/provider_settings.py`.
It is a proposed injection seam, not a change to common contract V1 or an implemented HTTP API.
The default `PendingSettingsClient` performs no reads, writes or provider calls. Pranit must
provide an authorized local service client and an approved production assembly entry point.
Tests alone inject `make_settings_client` in the Streamlit session.

- `read()` returns `SettingsSnapshot`: opaque UUID `revision`, fixed supported provider/model
  IDs, Cloudflare account ID, and two boolean key-presence flags. No keys or key fragments.
- `apply(SettingsChange)` uses `expected_revision`, the supported selection, and separate
  `keep`/`replace`/`remove` actions per key. Replace consumes a privately service-staged key
  bound to this local operator/revision. Missing stage or stale revision changes nothing.
- Persist changes atomically using the existing service configuration mechanism. Preserve
  unrelated settings and restrict file access. Removal must remove the stored key and stop its
  future use across API/workers; replacement must invalidate old runtime state. Define restart
  or reload behavior explicitly in the service response before marking integration complete.
- Use the existing authentication/owner boundary. Never introduce a second memory store or
  return provider keys to the viewer. The memory API token is a different credential.
- Do not enable capture, consolidation, paid execution, or change retention/request limits.
  Those operational choices are outside this phase. Applying settings requires an explicit
  confirmed action; reading, editing, validation and startup never apply configuration.

Actual settings persistence, private key staging/validation, runtime reload and cross-process
credential removal are **pending owner integration**, not demonstrated by the UI substitute.

`check(CheckRequest)` is also proposed for owner implementation. Validate `expected_revision`
before accessing keys. For probe `supported-provider-connectivity-v1`, perform one Groq
chat-completion request (`Reply OK.`, selected model, max output 32 tokens), then one Cloudflare
embedding request (`ContextBridge connectivity check.`, selected model). Fixed official origins
only; the Cloudflare path uses the validated account ID. At most two requests total under one
10-second elapsed deadline including all reads; stop on the first failure. No retries, redirects,
proxy inheritance, memory/database reads or provider body/credential logs. Enforce response-byte
bounds using the existing adapters. Honor the existing hosted/free-plan/paid-execution gates;
check consent cannot override account policy or enable processing.

Return `CheckReport` with checked revision, 1–2 attempted calls, and enum outcomes only:
`ok`, `authentication_failed`, `timeout`, `rate_limited`, `unavailable`, `invalid_response`,
or `not_attempted`. Never return provider text or exception detail. A stale revision must fail
before a network request. The viewer rejects mismatched revisions, unknown fields/outcomes,
inconsistent call counts and attempts after the first failure. The owner still must prove
actual transport limits, key syntax/authentication, atomic configuration changes and worker
reload/removal with isolated configuration and mocked provider transport before integration
is complete. No live check was authorized or performed during Phase 3 development.
