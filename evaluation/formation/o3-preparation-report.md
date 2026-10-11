# O3 preparation validation — no real-provider baseline

Recorded on 11 October 2026 from `codex/om-o3-provider-evaluation`, based on `develop` at
`2e22f176cf06e40514b66861c730d32aea77f06b` (merged O2 PR #13).
The user explicitly chose dataset preparation and left real-provider evaluation pending.

## Prepared inputs

Revision 1 contains 12 tuning cases and 12 fixed holdout cases, with 10 expected atomic claims
in each split. Both cover all six memory types. Inputs and excerpts are synthetic English
examples with explicit binding and stable IDs. Design labels still require team review.
Canonical fingerprints are recorded in [manifest.json](manifest.json); no input/case identity
is shared between tuning and holdout.

## Observed checks

| Check | Result |
| --- | --- |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 134 Python files checked |
| Alembic upgrade and `alembic check` | Passed on a newly created dedicated `_test` database |
| Full PostgreSQL pytest suite | 363 passed, zero skips, 49.62 seconds |
| Formation tests in that suite | 151 passed; 30 new evaluation tests and 9 PostgreSQL tests |
| Tuning recorded self-check | 12 cases; 10 expected/matched proposals; no admission/scope/provenance error |
| Holdout recorded self-check | 12 cases; 10 expected/matched proposals; no admission/scope/provenance error |

Environment: native Windows, Python 3.12.10 and local PostgreSQL 18. The full suite ran via
`uv run python scripts/formation/run_checks.py`, including migration regression round trips and
actual MCP subprocess tests. The disposable test database was retained for inspection; the
configured application database was not truncated/tested. Nine existing Alembic `path_separator`
deprecation warnings remain in shared configuration, which was not edited.

The evaluation tests check independent annotation matching, duplicate prediction accounting,
unsupported/uncertain claims, scope/provenance errors, empty denominators, stale review hashes,
fixed split identity, missing cases/labels, failure reporting, bounded files, secret-safe errors
and missing telemetry. The existing source-grounded formation/shared-engine tests also passed.

## What these results establish

Self-checks construct expected proposals from the labels and inject recorded support. Their
matching counts are deliberately circular fixture checks, not extraction precision/recall or
semantic verification measurements from a real model. Every report identifies recorded mode,
states that the runner executed no model, and leaves the quality gate pending.

No model ID, prompt version, inference latency, token usage or provider cost was observed.
Those fields remain null/missing; test runtime is not inference latency. No private conversation
or paid inference call was used. The scorer can validate explicitly supplied prediction/review
artifacts later, but does not execute a provider or verify the provenance of an external run.

Real provider/verifier selection and implementation, reviewed labels, approved baseline runs,
actual telemetry and agreed quality targets still remain O3 work. Targets must follow the initial
baseline and precede tuning. Production integration and O4 consolidation remain pending.
This report records completion of the requested preparation scope, not completion of O3 or V1.
