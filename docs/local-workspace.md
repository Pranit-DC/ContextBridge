# Local workspace and provider setup

The workspace brings memory controls and local provider settings into one place.
It uses the existing HTTP client/controller and shared memory API. Settings are
installation controls for the local operator, not a remotely writable API or a
second memory store.

## Start here

```bash
uv sync --frozen --all-extras --python 3.12
uv run python scripts/setup_ui.py
```

The setup launcher opens **Settings** on `http://127.0.0.1:8501`, even without
provider credentials or a running API. If `.env` does not exist, it uses the
existing setup helper to create private local service settings and agent snippets.
Existing installation settings are preserved. A custom `--env-file` must already
exist. Use `--port 8502` if necessary; `--project-id` overrides the viewed project,
otherwise the saved processing project is used.
Docker Compose must be installed and Docker running before Apply can start services.

1. Add a Groq key, select an offered model, and confirm your account's Free plan.
   Add a Cloudflare Workers AI token and its separate 32-character account ID.
2. Enable only the processing/search features you want, then **Save settings**.
   Saving validates configuration locally and makes no provider requests.
3. Open **Apply to services**, review the processing/restart notice, confirm and
   apply. This explicitly runs Compose build/up for the API and workers using the
   saved file. Existing memory volumes are retained. Enabled workers may process
   queued interactions and consume provider allowance.
4. Open **Memories** to check service readiness and configured capabilities.
   **Add memory** saves a confirmed statement with evidence or imports a chosen
   conversation. **Activity** contains consolidation and retired-memory controls.

Provider keys and the service access token have different purposes. The settings
screen never shows stored provider keys or sends them back as field defaults.
The separate Service connection expander uses the service access token; the local
file can supply that token without placing its value in a browser field.

The supported panel configures the existing **Groq compatible endpoint** and
**Cloudflare Qwen3 Embedding / 1024 dimensions**. It does not claim arbitrary
provider integration. Paid Groq execution remains disabled; Free-plan confirmation
is an operator attestation, not a billing guarantee. Custom factories/providers
are detected and preserved; this panel refuses to replace them.

## Key changes and configuration safety

Use **Manage key → Replace key** or **Remove key**. Blank fields retain an existing
key. Removal deletes the managed credential from the file and disables its provider
in the saved settings; disabling processing also disables automatic consolidation.
**Apply is required to stop running processes using a previously loaded key.**

Entered keys are cleared after both successful and failed submissions. They are
not placed in Streamlit caches, logs, public snapshots, request URLs, command
arguments, report screenshots or configuration history. The private dotenv file
stores credentials in plaintext: it is not an encrypted vault. POSIX replacements
use mode `0600`; on Windows, protect the checkout with appropriate account/file
permissions. The memory API has no provider-key/settings endpoint.

Changes use an exclusive advisory lock, a pinned file revision and a private atomic
replacement. A second window must reload after another save. Unrelated entries,
database credentials, comments and multiline values are preserved. Symlinked
settings/state files and malformed configuration are refused safely. Temporary
files are removed after failures; no backup containing removed keys is created.
External editors do not participate in the lock, so close them while saving.
Referenced credentials such as `${OTHER_KEY}` are not resolved from the shell or
silently requoted: replace/remove them explicitly, or manage that setup outside
this panel.

Apply uses a fixed local Compose file, no shell, and a sanitized child environment
so inherited provider variables cannot override saved values. A successful command
records the applied revision, **not provider quality or service readiness**. A
timeout/failure may leave some services changed; inspect Docker before retrying.
Apply/restart is available only when the selected file belongs to this installation.
Custom files elsewhere can be edited/tested with restart disabled.

## Explicit connection checks

Save first, then open **Check provider connections**. Each button requires explicit
consent and sends at most **one synthetic request**, never stored memories:

- Groq: a short structured evidence check, at most 512 output tokens.
- Cloudflare: one short synthetic embedding input, using the existing bounded backend.

Checks use fixed supported HTTPS endpoints, no redirects, no ambient proxies and
no automatic retries. Each has a ten-second timeout. The local allowance reserves
attempts before calling: one-minute cooldown across checks, at most three checks
per provider per UTC day, including failures. Consent resets after each attempt.
Provider quotas/charges can still apply. A passed check establishes that this
synthetic request worked; it does not approve extraction or retrieval quality.
The earlier stopped evaluation ledger is not reused or reset. Implementation and
report capture made **zero live-provider requests**; HTTP tests use substitutes.

## Deliberately small operational controls

The **Memory & processing preferences** expander exposes only supported settings:
processing project, interaction grouping, idle wait, maximum interactions per group,
raw interaction retention, optional consolidation and the daily processing-token
ceiling. Existing custom retention durations remain exact. Grouping does not install
a host hook. Host capture still requires its separate explicit setup and normal
host trust review. Consolidation uses the existing 15-minute bounded schedule;
no unsupported schedule editor or universal cost control is implied.

Saved memory is not deleted when raw interaction retention expires. Correction,
retirement, restoration and confirmed permanent forgetting keep their existing
evidence/version/scope safeguards. Changing connection/project clears memory
selection and drafts. The normal workspace renders only the selected task;
opening Settings makes no memory-service/provider request.

## UI and validation

The presentation uses a restrained light theme, one main task at a time, native
labelled controls, explicit text states, visible keyboard focus and progressive
disclosure. Scope, conditions and uncertainty remain visible on memory cards;
long technical source references remain available on demand. Optional search
filters and save conditions/time are collapsed. The provider grid wraps based on
available content width, and the narrow heading clears the fixed toolbar.

The setup launcher disables usage telemetry and detailed UI exception output and
uses the minimal Streamlit toolbar. Legacy V1 launchers now open the same workspace.
Those legacy full-V1 launchers intentionally enable their configured demonstration
runtime; use the setup launcher plus Apply for saved on/off preferences.

This is a single-user local operator interface. Keep its loopback binding and the
default Streamlit origin/XSRF protections; it is not authenticated multi-user or
public settings hosting. No claim of complete accessibility certification, clean
Windows Docker Desktop validation, independent usability approval or live-model
quality follows from automated tests.

The [report gallery](report/interface-screenshots.md) contains real browser captures
with synthetic data and clearly states their limits. The actual workspace widgets
have been exercised through the HTTP client and real API/PostgreSQL for save,
inspection, correction, retirement, restoration and permanent forgetting.

Final verification: **1,581 passed**, no skips or xfails, 86% coverage. Ruff check,
format check (383 files), locked dependencies, dedicated PostgreSQL test migrations
and schema drift check passed. Real Linux/Redis worker probes and MCP subprocesses
ran; 17 warnings are existing Alembic configuration deprecations. A separate
temporary-checkout check verified initial `.env`/adapter/snippet creation and the
settings-first launcher without provider credentials. These do not replace an
independent clean-machine walkthrough.

## Native Windows test portability

Settings round-trip coverage checks both LF and CRLF input explicitly, including
preservation of unrelated multiline dotenv bytes. Launcher assertions compare
native path components. These replace Linux-only test assumptions without
normalizing user files or changing launch behavior. Native Windows CI is distinct
from the pending Windows Docker Desktop walkthrough.

Portability verification: **1,582 passed**, no skips or xfails; 86% coverage.
Ruff check/format, locked dependencies and test-database migration/drift checks
passed. Native Windows CI verifies the actual Windows execution separately.
