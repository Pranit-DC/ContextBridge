# Phase 2 correctness review

PR [#38](https://github.com/Pranit-DC/ContextBridge/pull/38) was already merged by the user.
This follow-up starts from merged `develop` at `3e84ec9`, preserves the requested
`codex/remaining-task-phase2` branch, and targets a new normal PR to `develop`.
No merge or `main` change is performed by the reviewer.

## Findings fixed

| Finding | Resulting behavior | Regression coverage |
| --- | --- | --- |
| A finished leader could make a retryable follower fail permanently, or leave later members unprocessed after a crash. Diagnostics also rewrote the original leader outcome. | Worker execution derives bounded aggregate group state without changing each source job's outcome. Unfinished members resume through the leader, completed members stay idempotent, and exhausted retries terminate only unfinished members. | Retryable follower, bounded exhaustion, succeeded/deferred leader restart, direct engine restart, read-only inspection, legacy jobs when grouping is enabled |
| Transient failures could erase persisted time/evidence uncertainty after extraction. | Unresolved-time/evidence reason codes survive retries; supported claims still process and the source job retains its deferral. | Mixed ambiguous-date/supported claim, provider timeout, retry and final deferred status |
| Group membership discovery used one unbounded SQL `IN` list before chunked erasure. At allowed buffer sizes this exceeded PostgreSQL's bind-parameter limit and prevented forgetting. | Both membership discovery and erasure use bounded parameter batches, in the existing deletion transaction. | Real PostgreSQL selection with 65,537 IDs, whole frozen-group cancellation and another owner's untouched job; the fixture stores only a few actual captures, so this is not a large-store latency benchmark |
| A proposed explicit effective instant equal to the synthetic group anchor was mistaken for an event-time default and replaced by a later source timestamp. | An aware ISO instant quoted in the original supporting excerpt is preserved; ordinary defaults still rebind to their own source event. Admission still checks semantic support. | UTC/offset-equivalent explicit instants, later import, original event/message/interaction/evidence, units and identifiers |
| Overfetch for reranking also enlarged graph expansion, letting clear related context displace a direct contested match. | Direct candidates may be overfetched, but graph expansion consumes only the original caller's spare slots. Expansion provenance stays request-local, and related context remains after direct context. | Actual merged retriever and PostgreSQL repository at limits one and two; the direct result survives and graph context fills only a spare slot |
| Adding policy warnings to a valid 20-warning V1 response raised an error instead of returning eligible cards. | Warning union stays within V1's limit, prioritizes conflict/degradation flags, and marks overflow explicitly. Budget omission also marks edge-linked uncertain alternatives even when their stored state flag is clear. | Full warning capacity, conflict reranking, omitted-warning marker and context-budget omission |
| Query understanding treated topic nouns such as "project database" as another project name, and clarification could bypass ordinary secret rejection. | Common project descriptors remain topic text; explicitly named/quoted projects still cannot override the binding. Secret screening runs before clarification. | Real rich-retrieval boundary, explicit project/filter tests, rejected secret omitted from the error response |

The initial regression run reproduced ten failures in group/deletion/retrieval paths. A separate
source-time regression reproduced the accidental retiming. The fixes also retain tests for
forgetting after the first member commits, deletion/expiry during extraction, concurrent delivery,
saved extraction replay, and owner/project/condition/time isolation.

## Compatibility and scope

Common V1 message shapes, ingestion acknowledgement/replay identities, original evidence,
legacy keyword/MCP behavior, caller limits, exact stored-field validation and full inspection
remain intact. The ranking-policy injection interface remains unchanged. No dependency or
database schema change is needed; no Alembic migration is added. Teammate-owned formation,
retrieval and inspection implementations/tests remain untouched. No host hooks are installed.

The review does not change the deferred date/range or multi-event evidence cases, nor claim
live-provider quality, measured provider cost, or actual agent-host acceptance. These remain
the integration limits described in the original Phase 2 report.

## Verification

Focused checks passed before each implementation commit: 58 group/worker/write regressions,
60 deletion/group/ingestion/write regressions, 32 temporal tests, and 72 retrieval/API/MCP tests.
PostgreSQL tests use only disposable `contextbridge_phase2_review_test` on loopback port 55442,
in a separately created container; other worktrees and their databases are preserved.

Final code verified: `ffdb1ad`, native Windows / Python 3.12.10, real PostgreSQL 18.6 and
pgvector 0.8.7. No development/production database was used.

| Required check | Result |
| --- | --- |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed |
| `uv run alembic upgrade head` | Passed; existing schema head `a25f0138ce41` |
| `uv run alembic check` | Passed; no upgrade operations detected |
| `uv run --all-extras pytest --cov=contextbridge --cov-report=term-missing` | **1,459 passed, 4 skipped, 17 warnings**, 195.36 seconds; 87% parent-process coverage |
| Migration preservation/downgrade/upgrade regressions | Passed in the full suite on the disposable review database |

The four skips are the real Linux Celery prefork/isolated-Redis transport probes; native Windows
cannot execute them. Remote CI results are separate from this local record. The 17 warnings are
the existing Alembic `path_separator` deprecations. Database/HTTP/pgvector/worker lease behavior is
real integration; model boundaries use injected or recorded test substitutes. No hosted model
quality or actual provider cost is claimed. Test output is retained locally in the ignored
`.contextbridge/phase2-verification/correctness-review-full.log`.

The follow-up PR is normal, as requested, and is left for the user's review and merge.
