# Linux V1 verification — 14 October 2026

Work is isolated on `codex/pranit-v1-linux`, created from fetched `develop` at `a1c7f6b`.
The remote reliability branch contained the saved unfinished repairs. Om's pushed project guide
was already merged; no separate Windows implementation commits were visible when fetched. Pranit
confirmed that Om works on his own computer. This branch preserves that shared
history and adds the Linux workflow without changing Windows launch commands.

## What is connected

The Linux launcher starts the existing API, PostgreSQL, Redis, workers and viewer, checks API/schema
readiness and the exact project binding, and opens the browser after the viewer is ready. Existing
credentials/data volumes remain in place. A conflicting non-viewer port, invalid token or mismatched
capture project produces a clear failure. Only the API token/project are passed to the viewer's
ContextBridge environment; model/database settings stay in the service configuration.

The existing reliability changes in develop provide semantic relevance filtering, clearer save
feedback, plain-text import, recent processing activity and an opt-in Codex user-prompt hook.
This branch additionally fixes real-browser form clearing, replaces stale successful-save feedback
when conditions are invalid, and corrects the isolated Docker test to use the recorded query vector
matching the corrected memory. The cutoff is kept intact. No database migration, model SDK or core
service is added; contract V1 and the existing nine MCP tools stay compatible.

## Observed checks

- Full PostgreSQL 18/pgvector/Redis/all-extras Linux suite: **1,313 passed, no skips**, 87%
  parent-process coverage, with 17 existing Alembic configuration warnings. Tests also exercise
  the connectivity command with HTTP substitutes: exactly three calls on success, one on a
  first-request rate limit, no credential output and no reused-ledger continuation. The final
  remote check belongs to the exact PR commit, not an inferred earlier passing branch.
- Ruff lint/format and frozen lock/install dry run passed. Dedicated `_test` database migration
  upgrade and schema drift passed. Existing development databases were not used for tests.
- Isolated Docker: actual modules/importer, durable indexing, hybrid endpoint, correction,
  all-service restart with preserved history, retirement/restoration, forgetting and cancelled
  replay **passed with recorded providers**. The initial check's unrelated query vector after
  correction was correctly excluded by the relevance cutoff; its expectation was repaired.
- Actual Linux launcher: rebuilt/started the existing services and opened the viewer at
  `127.0.0.1:8501`, retaining the existing `panel-demo` binding. It confirms configuration, not model
  accuracy. No additional verification statements were submitted to live models through startup.
- Actual browser: an empty save showed a visible error and retained the Save tab. The reported
  token-access statement saved successfully in a separate synthetic project, its exact evidence was
  visible, and confirmation persisted after navigating away/back. Only that newly created synthetic
  memory was then forgotten; existing memories were preserved. No model requests were needed for
  this browser check because the project was outside the configured indexing/capture binding.
- The existing Codex MCP connection reported ready with its bound project. Codex hook configuration
  is generated but inactive: activation and the normal `/hooks` trust review remain user actions.
  Adapter tests and prior synthetic live processing do not establish an actual newly hooked host
  session. Claude remains pending by the user's earlier choice; Windows Docker Desktop is separate.

## Today's bounded online check

Automatic approval review initially blocked new live requests because the original V1 run had
stopped after a provider failure. Pranit then explicitly approved a **new separate check of at most
one Groq and two Cloudflare requests**, stopping on failure and preserving every earlier ledger.
That exact check completed: **1 Groq / 2 Cloudflare**, all successful. No saved memory was sent.

The [synthetic report](v1-evidence/linux-connectivity-20261014.json) records the original report hash,
numeric counts, Groq HTTP observation and Cloudflare similarity matrix. Groq returned a valid
`supports` object; Cloudflare enforced 1024 finite dimensions. Against three synthetic documents:

- Database query matched the database document at cosine 0.6187.
- Language query matched the Marathi preference at 0.4713.
- API-access query matched the token requirement at 0.6037.
- Donald Trump and cooking queries had all similarities below 0.18, below the configured 0.4 cutoff.

These are small connectivity/relevance observations, not a general accuracy percentage or a
fresh complete online lifecycle test. No further live verification calls were authorized/performed
in this run. Earlier duplicate/evidence-check failures are not erased or claimed fixed by these
three requests. Free-plan status is the user's attestation; billing was not independently measured.

Follow [the Linux usage guide](linux-v1.md) to enter arbitrary statements and inspect actual outcomes.
Unsupported, ambiguous, oversized or secret-containing inputs still require visible rejection or
pending status. No fixed demonstration text is used as an application answer.
