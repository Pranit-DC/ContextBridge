# ContextBridge local product

The browser workspace replaces Streamlit as the default end-user interface. It uses
Next.js/React static assets and a native Python manager bound to `127.0.0.1`.
The existing API, workers, PostgreSQL and MCP adapter remain the memory authority.
Streamlit remains available as a legacy interface; managed credentials cannot be
written through its old settings form.

## Install and start

Use Linux with Docker Engine or Windows with Docker Desktop **Linux containers**.
Install uv and unlock your OS credential store. Linux requires a desktop Secret
Service (for example GNOME Keyring) and a session D-Bus connection. Windows uses
Credential Manager. Null, plaintext, chained and third-party keyring backends are
refused. Headless Linux must provide an unlocked Secret Service session; otherwise
AI configuration is unavailable. Memory-only mode remains available.

From the unpacked release directory:

```text
uv sync --frozen --no-dev --extra product --python 3.12
uv run contextbridge start
```

Keep the launcher running. It opens a short-lived, one-use browser link; the token
is removed from the address after exchange. Repeating `contextbridge start` reopens
the running manager. `--no-browser` prints a private launch link. Do not share it.
`uv run contextbridge status` reports services. `uv run contextbridge stop` stops
services and the manager while preserving memory volumes. Closing the browser does
not stop background services. Closing the manager does not erase memory.

Source contributors first run `npm ci` and `npm run build` in `frontend/`.
Node is needed to build, not to use a prebuilt release. Run the Python commands
from the installation directory, or supply `--root` with its absolute path.
Only local Unix-socket/Windows-named-pipe Docker endpoints are accepted. A conflicting
Compose project from another installation is refused. Existing orphaned volumes
require ownership review; the launcher never deletes or silently adopts them.
Ports 8000 (memory API), 8501 (workspace) and 5433 (database) must be available.

## First use

1. Open **Settings**. Review the data flow, choose supported models and save keys
   into native secure storage. Saving does not contact a provider.
2. Select processing/search options, review the consent and **Apply and restart**.
   Memory-only startup disables hosted processing and search by meaning.
3. In **Connections**, enter an existing workspace and preview the project-scoped
   Codex user-message hook. Enable only after reviewing the change. Complete Codex's
   normal workspace trust/restart flow. Pause/remove only removes our hook.
4. Generate MCP instructions for another host, using the same project ID. These
   expose tools; automatic conversation capture is a separate opt-in integration.
5. Chat normally in the connected, trusted project. Inspect **Activity**, then
   **Memories**. Queued means accepted for processing, not successfully extracted.

**Add memory** supports an explicit evidence-backed write, your own original
statement, a JSON conversation retaining speakers, or a V2 evidence bundle. V2
requires its Settings switch and original timestamps/timezones. See
[evidence/time V2](evidence-time-v2.md) for the exact schema and model limitations.
Do not relabel assistant output as a user statement. Retries reuse unchanged event
and request IDs; start a new request before changing an uncertain submission.

## Control your memories

Choose a project and explicitly switch it. Browse current memories or search with
conditions/time and optional shared developer memories. Open a card to inspect
sources, version history, relationships and uncertain/conflicting alternatives.
Corrections require fresh evidence and an expected version. A stale correction
preserves its draft and requires review of the current version before retrying.
Retirement excludes current use while preserving history; restoration creates a new
version with fresh evidence. Permanent deletion requires typing DELETE and removes
stored content, evidence, history and related records through the existing engine.
Forget also clears workspace drafts/caches. This does not erase copies previously
sent to providers, agent hosts, user backups or other applications.

**Activity** shows job progress and explicit refresh/poll controls. Consolidation
and duplicate retirement use existing guarded preview/confirm operations. Semantic
merging and selective verification can call providers only after explicit consent;
uncertain output is refused. They do not establish general model quality.

## BYOK trust and migration

Provider keys go from a password field to the loopback manager, then native OS
secure storage. The browser never receives saved keys or stores entered keys in
local/session storage. New key fields clear after submission and navigation.
A service restart passes secrets on Docker exec stdin into a private container
`tmpfs`; provider values are excluded from Docker environment and command arguments.
Consumers restart together; partial handoff failure pauses them. After a container
restart clears tmpfs, apply again to deliver keys. Replacing/removing keys pauses
old consumers before saving. Saving/applying have separate, explicit controls.

Existing plaintext provider entries require **Migrate existing keys**. Consumers
pause; the manager writes and verifies one native bundle before removing only those
provider bindings from `.env`. No plaintext backup is created. If file cleanup
fails, the old file remains and migration must be retried. Infrastructure API tokens
and database passwords remain private local files: this is not an all-secrets vault.
Never commit `.env`, `.env.mcp` or `.contextbridge`.

This is a local single-user trust boundary. It does not defend against malware,
other processes authorized as your OS user, browser compromise, Docker administrators
or a compromised dependency. OS vault policy controls encryption/unlock; tmpfs may
be swapped by the host. Provider requests send selected text/evidence to Groq and
Cloudflare according to enabled features and their policies. No zero-knowledge,
zero-retention or independent-security-audit claim is made. No analytics, remote
fonts or third-party scripts are loaded by the workspace.

## Recovery and acceptance

Unlock secure storage and reload after a lock/timeout. A timed-out vault write may
have succeeded; reload before retrying. Drafts survive page navigation within the
workspace, not browser reloads; provider keys are never drafts. Review Activity
after a lost job response. Refresh a stale version explicitly. Provider checks are
manual, bounded by the existing daily ledger, and may consume quota. They are not
run on startup. Offline tests cannot approve hosted model quality.

Release checks include Python regression tests, real PostgreSQL browser CRUD,
Chromium keyboard/responsive/accessibility checks, isolated Docker credential
handoff, native-vault probes and a clean release installation. Actual Windows
Docker Desktop, actual host trust/Claude onboarding, first-user usability and
representative live model evaluation still require acceptance evidence. Hosted
accounts, remote MCP, public SDKs, native installers and extra automatic capture
adapters remain outside this milestone.

## Verified implementation evidence (30 October 2026)

- Full dedicated PostgreSQL 18/pgvector + Redis regression: 1,777 passing tests,
  no skips/xfails, 84% coverage and 20 existing Alembic warnings. The two final
  manager concurrency/timeout cases bring the targeted product set to 30 passing
  tests; these were added after the full run collected its cases.
- Six Chromium workflows pass, including two-page stale correction recovery and
  project draft isolation. Desktop/mobile axe scans report no violations.
- Real Linux Secret Service: native bundle round trip, rotation, actual authenticated
  settings HTTP save, response/file secrecy and deletion all pass in an isolated
  temporary keyring. No existing provider entry was used.
- Disposable Docker network with provider egress blocked: managed startup,
  actual runtime configuration, empty provider environment, private tmpfs,
  rotation/recreation and memory-only restart pass. Its vault was synthetic.
- Clean release install and bundled UI/CSP serving pass without Node or provider
  keys. Production frontend build, generated API types and typecheck pass.

Screenshots are in [the report](report/interface-screenshots.md). Native Windows
secure-storage CI and complete CI status must be checked on the PR; this local
Linux evidence does not establish Windows Docker Desktop or hosted model quality.
