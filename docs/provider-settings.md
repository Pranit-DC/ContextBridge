# Local supported-provider settings

The shared service implements authenticated settings reads, revision-checked updates and a
bounded connection check for Groq `openai/gpt-oss-120b` and Cloudflare
`@cf/qwen/qwen3-embedding-0.6b` (1024 dimensions). The viewer uses these real endpoints by default.
Custom factories, arbitrary provider endpoints/models and new operational controls are excluded.

## Enable private configuration deliberately

Set `CONTEXTBRIDGE_PROVIDER_SETTINGS_FILE` in the service environment to an **absolute `.json`
path in a dedicated private directory**. Native installations can use a new directory under
their user profile; do not point this at `.env`, an existing shared directory, or a network path.
For Compose use `/var/lib/contextbridge/providers/providers.json`. The supplied API, worker and
scheduler mount the same `provider_settings` volume. All processes must share the path, developer
identity, API token and existing execution-policy settings. Recreate containers after enabling
the path; subsequent key changes need no restart.

An empty/unset path retains the existing environment-based provider configuration and disables
settings writes. Enabling the path makes this file authoritative for provider credentials:
legacy environment/dotenv keys are ignored, including after removal. There is no automatic key
import, dotenv edit, installed-agent edit, file creation or online check at startup/read time.
Formation/capture, consolidation, retention, bindings and hosted/free-plan/paid policy switches
are preserved. Applying keys can resume processing that the operator already enabled/bound.

The file is plaintext local service configuration, not an encrypted vault or a memory store.
Directories/files require owner-only POSIX permissions (0700/0600), or a protected Windows DACL
granting only the current user and SYSTEM. The service creates its new private directory on an
explicit staging/apply action and rejects insecure existing permissions, links, malformed data
and mismatched developer ownership. Exclude this directory/volume from shared archives and logs.
External environment values, backups and third-party copies have separate retention policies.

## Stage privately, apply explicitly

Use the same local service environment, including its existing ContextBridge API token. That
token authenticates memory/settings operations; it is **not** a Groq or Cloudflare credential.

```text
uv run python -m contextbridge.provider_configuration show
uv run python -m contextbridge.provider_configuration stage --provider groq --expected-revision UUID_FROM_SHOW
uv run python -m contextbridge.provider_configuration stage --provider cloudflare --expected-revision UUID_FROM_SHOW
```

`show` prints only public selection, revision and presence flags. Staging requires an interactive
masked prompt; keys are never command arguments, browser inputs, HTTP bodies or CLI output.
The stage is bound to the configured developer, current revision and current API-token identity.
It validates printable credential syntax, rejects the memory API token as a provider key, and
does not activate the staged credential. Stale revisions and missing replacement stages fail
without changing active configuration. A staging command reports safe errors without raw input.

With Compose, run the equivalent commands in the service container, using `docker compose exec
-it api python -m contextbridge.provider_configuration ...` for the masked staging prompt.

In **Provider setup**, load the current settings, enter the Cloudflare account ID (32 hexadecimal
characters), select **Keep current key**, **Use staged replacement**, or **Remove key**, then
confirm and press **Apply provider settings**. These are developer-wide settings across projects.
Updates atomically replace the private file with a new revision and consume all staged keys.
Removal deletes the active key, staged values and abandoned writes for that store; no backup
versions are created. Unrelated service settings and `.env` files are preserved.

Concurrent updates have one revision winner. After a lost response, reload before retrying.
API requests and worker executions construct fresh providers from the shared file. A final
cross-process lock/revision fence prevents stale clients from dispatching an old credential after
an update is acknowledged, including clients that waited for quota. An already-dispatched
request can finish; future dispatch is rejected. The service retains no global credential cache.

## Validate and check

Offline validation checks selection and presence only. It neither authenticates keys nor reads
memory data. To check online, read the disclosure, explicitly consent and press the check button.
The existing service policy must permit hosted Groq execution, attest its free plan and disallow
paid execution. Consent cannot override these settings; billing/account status is not queried.

The check sends only `Reply OK.` to Groq (at most 32 output tokens), then
`ContextBridge connectivity check.` to Cloudflare. It sends account authentication and consumes
provider quota; provider data policies apply and actual account billing remains the operator's
responsibility. No saved memory, evidence, conversation, draft or database content is read/sent.
There are at most two HTTPS requests, no retries/redirects/proxy inheritance, a 2 MiB response
bound, and a stop on the first failure. A separate child receives credentials through a private
stdin pipe and is killed at the overall 10-second deadline. Its stdout contains only fixed
progress/outcome enums; credentials never enter its arguments, environment or report files.
Authentication, timeout, quota, invalid response and unavailable outcomes have safe labels.
This checks connectivity, not semantic quality or billing guarantees.

## HTTP boundary and verification

All routes use the existing bearer authentication and configured developer identity:

| Method/path | Behavior |
| --- | --- |
| GET `/v1/provider-settings` | Public snapshot; no key values/suffixes/fingerprints |
| PUT `/v1/provider-settings` | `SettingsChange` with expected revision and explicit key actions |
| POST `/v1/provider-settings/check` | Fixed `CheckRequest` with expected revision and bounds |

No HTTP key-staging endpoint exists. Responses forbid unknown/private fields. Errors expose
fixed codes only, without rejected fields, paths, exception bodies or SQL details. The memory
store/schema and common memory contract V1 are unchanged; no Alembic migration is needed.

Tests use synthetic credentials, private temporary files and mocked provider transport. They
exercise the real API/viewer client, restart/replacement/removal, permissions, concurrency,
stale dispatch, malformed output, child deadline enforcement and safe errors. Development does
not read/change existing real credentials, `.env` files or installed host configuration and
does not run live provider calls. See [Phase 3 verification](inspection/phase3-verification.md)
for final required-check results and the separate human accessibility/live-quality limits.
