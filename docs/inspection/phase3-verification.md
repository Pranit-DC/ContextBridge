# Remaining tasks Phase 3 verification — 29 October 2026

> Historical viewer-only report. The [30 October settings integration verification](phase3-settings-verification.md)
> supersedes the pending integration and failed-check status below.

Published branch: `codex/remaining-task-phase3`, created from the latest fetched develop
and rebased onto `d0c7d99` before its first push. After Phase 2 landed, the same patch was
tested locally rebased onto `3e84ec9`, preserved as `codex/remaining-task-phase3-verified`.
GitHub prohibits force-pushing this PR branch, so published history was retained and this
verification report was added with a normal follow-up commit. Inspection source/tests on the
published and verified branches are identical (`git diff --exit-code` passed for those paths).
Work used an isolated checkout. Changes are limited to inspection source/tests/docs;
shared API/configuration, common contracts, provider implementations and storage are unchanged.
No branch/PR was merged and `main` was not modified or pushed.

## Delivered and checked locally

- Fixed Groq `openai/gpt-oss-120b` and Cloudflare `@cf/qwen/qwen3-embedding-0.6b` setup.
  Loading/offline validation do not mutate settings or call providers. Explicit confirmed
  actions distinguish keeping, replacing and removing credentials, using revision checks.
- An injected settings client carries public metadata/key-presence flags only. The production
  fallback explicitly reports pending integration. It has no file writer or credential store.
- Unknown/secret-bearing response fields and malformed model instances are rejected. Errors
  discard raw transport/provider detail and exception context. No provider key value/suffix,
  shared cache, credential screenshot or secret-bearing report is produced.
- The online-check UI discloses exact synthetic text, account authentication, quota/cost and
  data implications before explicit consent/button action. The proposed request fixes two
  calls maximum, a 10-second overall deadline, 32 Groq output tokens, no retries and a stop
  on the first failure. Actual transport enforcement is pending shared service integration.
- 53 new tests extend viewer automation to 192 cases. They cover setup/settings, safe failures,
  missing/malformed/replaced/removed public configuration, saved-versus-draft checks,
  auth/timeouts, lifecycle/status/error/recovery and an accessibility subset. Drafts now survive
  readiness outages and review of a newer memory version. Writes still require explicit actions.

All development credentials were synthetic. New widget tests clear inherited provider/viewer
credentials and block unmocked HTTP transport. Configuration-file checks use pytest temporary
files; existing `.env`, `.env.mcp`, provider keys and installed host configuration were untouched.
No live provider request was made. No optional operational controls or arbitrary providers added.

## Required repository checks

The frozen lockfile's all-extras environment used Python 3.12.10 on native Windows. Integration
checks used a newly created `contextbridge_phase3_test` database with a synthetic dedicated role
in the existing disposable PostgreSQL 18/pgvector test container. Both database environment
variables pointed only to this `_test` database; `CONTEXTBRIDGE_REQUIRE_VECTOR=1` was set.
No migration downgrade or destructive integration test ran against real memory data.
After verification, only this task's disposable database and synthetic role were removed;
the pre-existing test container and other databases were preserved.

- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed (349 files on the latest base).
- `uv run alembic upgrade head`: passed.
- `uv run alembic check`: passed; no new upgrade operations.
- `uv run --all-extras pytest --cov=contextbridge --cov-report=term-missing`:
  **1492 passed, 1 failed, 4 skipped, 17 warnings** in 257.58 seconds on the latest rebased code.
  All 192 viewer tests passed. Parent-process coverage was 87%; AppTest's runpy execution
  of `app.py` is not reflected in that file's coverage percentage. The 17 warnings are the
  existing Alembic `path_separator` deprecation. Migration preservation/round-trip tests passed.

The latest full run failed
`tests/integration/test_graph_depth.py::test_backtracking_cannot_starve_forward_neighbors_or_exceed_limit[1]`
at line 72: the final single-card result carries `RELATED_MEMORIES_INCLUDED` although no related
card survives its final limit. The card-count/identity assertion passes; the warning assertion
fails. A focused database rerun reproduced this failure. Its test, shared retrieval service,
retriever, graph expansion and repository all match `origin/develop`; none is changed in Phase 3.
Shared retrieval ownership must resolve the mismatch between expanded candidates and the final
warning. The full latest-base suite is **not green**. An intermediate full run on `d0c7d99`
(before Phase 2 landed) passed 1416 tests with four skips; it does not replace the latest result.

The first full run, before rebasing onto the newer develop, had 1361 passed, one failed and
four skipped. The unchanged shared test
`tests/test_v1_demo_budget.py::test_concurrent_clients_share_the_ceiling_and_crash_reservations`
failed at `scripts/v1/budget.py:26`: Windows `msvcrt.locking` raised
`OSError: [Errno 36] Resource deadlock avoided`. One focused rerun reproduced it. Both files
match `origin/develop`; this phase does not change the shared budget implementation/test.
The later full runs passed that budget test without any budget-code change. Retain the two earlier
failures as evidence of intermittent Windows locking behavior for its owner to investigate;
those passes do not explain or fix the intermittent locking failures.

## Precise pending integration and review

Pranit must implement/approve authenticated local settings-client assembly, public settings
reads, private key staging and syntax validation, atomic revision-checked persistence, and
credential replacement/removal across running API/workers. The owner must enforce the actual
bounded check transport, fixed official endpoints/synthetic inputs, response bounds and existing
hosted/free-plan/paid-execution policy. The proposed seam and mapping are in
[the integration request](integration-request.md#5-supported-provider-settings).
Fixture results do not prove real configuration persistence or credential invalidation.

The four Linux prefork/Redis transport probes are unavailable on native Windows. A real
settings-service check, supported-platform browser walkthroughs, Windows full-stack walkthrough
and a human accessibility review remain pending. Automated widget checks cover visible names,
password masking and text feedback only; they do not establish keyboard/focus behavior,
contrast, zoom or screen-reader announcements. Keep the PR a draft until essential owner
integration and verification are resolved. No merge is authorized by this report.
