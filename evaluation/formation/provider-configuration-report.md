# User-configurable provider validation

Recorded on 11 October 2026 from `codex/om-user-configurable-provider`, based on `develop`
at `a093059d405a376fad4ecbed4f70f821560009a5`. The user approved provider/model selection and
their own API key; they have not authorized real model evaluation or chosen a paid budget.

## Implemented scope

Formation-local dotenv/environment settings, key-masked configuration inspection, injected
Chat Completions extraction and separate evidence-verification calls, and an explicitly opt-in
proposal/admission runner. OpenRouter free-only requests constrain prices to zero, disable
fallback, require supported parameters and default to denied data collection. Local loopback
Ollama and explicit compatible endpoints are selectable. Credentials are excluded from settings
serialization and sent only as an authorization header. No model/provider defaults are selected.

The API, viewer, workers and shared settings still need owner integration. No shared file or
contract was changed; no formation persistence, conflict mutation or credential store was added.

## Observed checks

| Check | Result |
| --- | --- |
| Ruff lint | Passed |
| Ruff formatting | Passed; 183 Python files |
| Dedicated database migration upgrade | Passed |
| `alembic check` | Passed; no new upgrade operations |
| Complete pytest suite | **738 passed, zero skipped**, 60.85 seconds |
| Formation tests | 220 passed, including 69 added cases |
| Optional viewer AppTest module | All 15 tests ran and passed |
| Actual loopback HTTP protocol test | Passed against a synthetic response server; no inference |
| Local key check | Key present, not a placeholder; provider/model missing at inspection time |

Full checks ran with `uv run python scripts/formation/run_checks.py` on native Windows,
Python 3.12.10 and PostgreSQL 18 with pgvector. The stopped database service was started using
latest develop's existing Compose configuration, preserving its named volume. Migrations and
test truncation ran only on a newly created dedicated `contextbridge_om_*_test` database; it
was retained for inspection. No migration/test command targeted the application database.
Thirteen existing Alembic `path_separator` deprecation warnings remain in shared configuration.

The first full run exposed the merged viewer's missing optional Streamlit package. Streamlit
1.65.0 (the viewer team's tested version) was installed only in the ignored local environment;
manifests and lockfiles were not edited. The next run exposed the formation check runner passing
the service token into the viewer's no-token test. The owned runner now removes that environment
token only for pytest; API tests provide explicit synthetic authentication. A new regression test
checks database isolation and this credential boundary. The final complete run above passed.

Tests cover environment/file precedence, key masking, explicit hosted/paid opt-ins, free model
binding, URL restrictions, no-network configuration checks, request routing/header shape, closed
schemas and condition conversion, actual loopback transport, comparison/admission handoff,
semantic disagreement, invalid provenance, duplicate IDs/conditions, refusal/tool output,
truncation, malformed/duplicate/non-finite JSON, secrets including escaped configured-key echoes,
bounded responses, HTTP errors, timeout, redirect rejection and missing/zero telemetry.

## Quality and integration remain pending

All semantic provider responses in tests were synthetic/recorded. Loopback networking checks HTTP
behavior, not a real model. No inference account authentication, download, private transcript or
paid call was performed; the user's key was never used for inference and `.env` was not edited.
OpenRouter catalog/documentation lookup was read-only and credential-free.

Actual model/endpoint compatibility, semantic quality, independently reviewed dataset labels,
observed baseline/latency/tokens/cost, agreed quality targets and production API/worker/viewer
wiring remain pending. There is no general currency budget enforcement; paid operators must set
a provider-side hard limit. The client exposes nullable per-call observations but does not prove
external provenance or replace human quality review. This change does not complete O3 or V1.

All merges are reserved for the user.
