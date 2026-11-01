# Hosted embedding verification — 12 October 2026

The [Cloudflare Qwen live report](cloudflare-qwen3-20261012.json) records the explicit capped
synthetic run against a fresh `contextbridge_embeddings_live_test` database. It sent 10 sequential
requests, using the user-confirmed Free account, and did not send existing private memories.
Cloudflare returned vectors of the required width, 1024. The intended database memory ranked first
for the paraphrase among three distractors. Fresh MCP SDK sessions saw correction, history, and
forgetting. API/MCP were exercised in process; the provider HTTPS and PostgreSQL were real.
The report hashes the adapter and probe sources used. It contains no API key or account URL.

Regression validation for this branch:

| Check | Observed result |
| --- | --- |
| Full suite, Python 3.12.13 / PostgreSQL 18 / real pgvector / Redis / all extras | 1126 passed, no skips, 90% parent-process coverage |
| Full suite, PostgreSQL 17 / real pgvector / Redis / all extras | 1124 passed, no skips, 90% parent-process coverage; the two subsequently added worker/request-bound tests also passed separately |
| Actual embedding-only Celery prefork worker, synthetic Cloudflare HTTP | Starts without a custom factory, indexes 1024-wide vectors, leaves capture attempts at zero; passed on PostgreSQL 17/18 |
| Disposable Compose stack with recorded merged-module backends | Import, indexing, correction, all-service restart, preserved history, forgetting, and replay fence passed |
| Alembic schema drift and downgrade-base/upgrade-head | Passed on disposable PostgreSQL 17 and 18 `_test` databases |
| Ruff lint/format, frozen dependencies, `uv lock --check`, diff whitespace | Passed; no dependency or migration change |
| Changed-file credential scan | No configured private API key/token/password/account URL found |

Existing Alembic `path_separator` deprecation warnings remain. Subprocess worker/widget execution
is not included in parent-process coverage. Ordinary regression tests use synthetic provider HTTP
and clear hosted credentials/model settings, including in worker subprocesses. The Compose probe
also overrides hosted credentials explicitly; no ordinary check spends Cloudflare quota.

This demonstrates the selected embedding flow, not general model accuracy. Installed Codex/Claude
Code host tests, Windows Docker Desktop checks, viewer semantic search, formation-provider runtime
assembly, and final product-quality/release gates are separate work. CI results belong to the exact
PR revision and should be checked before merging. See [setup/recovery](../../docs/cloudflare-embeddings.md).
