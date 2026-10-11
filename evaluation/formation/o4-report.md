# O4 consolidation validation — 11 October 2026

Prepared on `codex/om-o4-consolidation` from latest `develop` at `86d93e0`, which includes
the manually merged provider/evaluation PR #22. This branch does not include unmerged O3
follow-up changes. No branch or PR was merged by the agent.

## Delivered behavior

The actual Om Consolidator implements the unchanged V1 dictionary entry point with injected
grouping and semantic-verification providers. Exact scope/project/conditions partitioning happens
before provider execution. Extractive summaries preserve complete distinct type/content pairs,
negation, units, filenames and rare details, citing every source version and deduplicated source
reference. No free-form model text becomes summary content. Stable proposal IDs bind snapshots.

Contested records, same-key differences, unsupported/uncertain meaning and overlong summaries
remain atomic. Missing evidence, ambiguous scope, sensitive text and malformed/forged output fail
safely; stale versions fail before a provider call. Unrelated singletons remain original records.
The shared engine owns all writes, conflict mutation, authorization and live-source fencing.
See [policy and limitations](../../docs/formation/consolidation.md).

## Recorded checks

| Check | Observed result |
| --- | --- |
| `uv run ruff check .` | Passed on native Windows and Linux |
| `uv run ruff format --check .` | Passed on native Windows and Linux |
| `uv run alembic upgrade head` | Passed against dedicated PostgreSQL `_test` database |
| `uv run alembic check` | Passed; no new upgrade operations detected |
| `uv run --all-extras pytest --cov=contextbridge --cov-report=term-missing` | 879 passed, 0 skipped, 0 errors/failures |
| Formation tests within full suite | 301 passed, including 75 new O4 tests |
| New isolated unit/scenario tests on Windows | 67 passed |
| Synthetic consolidation runner | 8/8 design-labelled scenarios matched expected proposal counts |
| Existing formation write regressions | Passed: ingestion replay, admission deferral and engine mutations |
| New actual formation-to-consolidation database regressions | 8 passed: replay/provenance, abstention, update/forget during both provider stages, derived-summary cleanup |

The full run used Docker Desktop Linux, Python 3.12.15, a fresh isolated
`contextbridge_om_o4_test` PostgreSQL 18 database with pgvector 0.8.7 and Redis 7.4.6.
The all-extras environment enabled viewer, workers and vector checks without editing dependencies
or lockfiles. All three Linux prefork worker probes ran against real Redis; no database or
platform-dependent test was skipped. Migration upgrade/downgrade regressions ran only in this
dedicated test database. The application database/container and `.env`/`.env.mcp` were untouched.

Repository line coverage was 90%; it is not a semantic quality measure. The run emitted 17 existing
Alembic configuration deprecation warnings about `path_separator`. No shared file was changed
to suppress warnings. The local JUnit artifact is `.pytest_cache/formation/o4-linux-suite.xml`
(ignored, not committed). Disposable O4 test containers/network were removed after verification.

## Limits and review gates

These are real PostgreSQL/engine executions using the actual Om module with injected synthetic
grouping and evidence labels. They establish deterministic policy, bounds, replay, source edges
and deletion/update behavior. They do not establish real model grouping/verification accuracy,
production factory wiring, or a human-approved end-to-end semantic pipeline.

`consolidation-cases.json` has eight synthetic **design** labels, not independent human labels.
The runner never calls a model, loads credentials or writes memory. No actual model latency,
tokens or cost were measured for O4. Repetition alone does not make a fact important; the rare
backup lesson survives even with an absent confidence score.

Pranit/team review of the integration handoff, an approved semantic grouping/verifier pair and
production factory configuration remain pending. O3 still needs a reliable baseline, independent
review, agreed condition-key/duplicate conventions and approved quality targets. Different-key
contradictions depend on the injected verifier; source excerpts and confidence are insufficient.
No paid provider or private-data behavior was selected or exercised. Shared requests are recorded
in [integration-request.md](../../docs/formation/integration-request.md).
