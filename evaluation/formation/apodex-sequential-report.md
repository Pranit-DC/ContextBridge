# Apodex sequential evaluation and test report

The user selected `apodex/apodex-1.1-mini:free` for continued O3 testing and required one request
at a time. This change adds its fixture profile and a serialized, paced, quota-bounded evaluation
runner. The tuning dataset, fixed holdout, design labels, manifest and `formation-chat-v2` prompt
are unchanged. No live holdout rerun or prompt tuning was performed.

## Actual synthetic tuning attempt

The run was recorded at `2026-10-11T19:38:08.754152Z` (12 October in Asia/Calcutta).
It used process-only overrides for Apodex extraction/verification and `json_object`, preserving
`.env`/`.env.mcp`. Paid use was disabled; OpenRouter routing required zero prices, no fallback,
supported parameters and `data_collection=deny`. No private transcript or memory write was used.

The authenticated key's safe quota snapshot showed 32/50 free requests used, 18 remaining before
the run; afterwards 35/50 used, 15 remained. The run allowed at most 16 calls with concurrency 1,
at least 3.1 seconds between starts, and no automatic retries. It actually made **three calls**:

| Call | Stage/case | Result | Latency | Input/output tokens | Reported USD cost |
| --- | --- | --- | --- | --- | --- |
| 1 | Extraction, database choice | Valid source-bound proposal, HTTP 200 | 7.735 s | 1140 / 986 | 0 |
| 2 | Verification, database choice | `supported`, HTTP 200 | 3.015 s | 677 / 271 | 0 |
| 3 | Extraction, disabled flag | Retryable `PROVIDER_UNAVAILABLE` after HTTP 200 headers | 35.563 s | Unknown / unknown | Unknown |

The two successful calls reported the observed model `apodex/apodex-1.1-mini:free`. The failed
call did not return a usable model/usage envelope; its observed model/tokens/cost remain null.
HTTP 200 headers alone do not prove successful inference. The unavailable failure arose while
finishing/reading the response; the exact upstream cause is unknown. No HTTP 429 was recorded
and the daily quota snapshot still had 15 requests remaining, so daily quota exhaustion is not
an established cause. Configured timeout was 30 seconds per operation plus an elapsed-response
check; observed failed-call wall time exceeded 30 seconds. This is not a strict total deadline.

Of 12 tuning cases, two reached the network: one completed both stages and produced one validated
proposal/ADMIT; one failed. Nine later network-eligible cases were **not attempted** because the
failure stop activated. One assistant-only case was blocked locally with no call. The ten cases
with safe unavailable error codes must not be reported as ten actual failed inferences: only one
was attempted and failed. The completed case took 10.750 seconds end to end; the failed case
took 35.657 seconds, including pacing/local overhead. Call latency excludes pacing.

Known usage was 1817 input and 1257 output tokens across two calls, with reported cost USD 0.
The third call's usage/cost is unknown, so **whole-run usage and cost are unknown**, not zero.
One model-supported proposal is not an independently reviewed true positive or accuracy score.

Evidence is in the immutable [predictions](apodex-tuning-sequential-20261012.json) and
[per-call/per-case telemetry](apodex-tuning-sequential-20261012.telemetry.json). The sidecar binds
the canonical run hash `7869cf02bc41f4fbb42bf79005bb80fa4ab4ec8b615a55b530b7580314c41731`
and tuning hash `c98957503bea13f4b5c52741fd889f2dffdbd9b03576744327549e2103f6b192`.
Generated proposals in these files are untrusted review artifacts, never stored project facts.

## Automated validation

The [Apodex test matrix](../../docs/formation/apodex-test-plan.md) covers all 24 fixed scenarios
using synthetic HTTP fixtures, the selected JSON-object profile, safe transport/usage handling,
verifier disagreement, status/timeout failures, request spacing, serialized budget checks,
cross-process evaluation exclusion, immutable exports and explicit unexecuted-case labels.
Fixture outputs and recorded verdicts measure protocol/policy behavior, not Apodex accuracy.

Validation completed on 12 October 2026:

- Focused native transport/profile/runner suite: **100 passed** with no skips.
- Complete Docker Desktop Linux/Python 3.12 all-extras suite: **934 passed**, including
  **356 formation tests**, with **zero failures, errors or skips**. This adds 55 tests to the
  merged O4 baseline. XML totals were checked explicitly; overall source coverage was 90%.
- `uv run ruff check .` and `uv run ruff format --check .` passed on Windows and Linux.
- Fresh dedicated `contextbridge_om_apodex_test` PostgreSQL 18/pgvector 0.8.7 database:
  `alembic upgrade head` and `alembic check` passed; migration revision `71e473f5df6d` was
  confirmed. Real database formation integration, migrations and vector tests ran.
- Isolated Redis 7.4.6 broker database 15: real prefork worker probes ran; viewer extra/tests
  were enabled through locked `uv sync --frozen --all-extras`, without manifest changes.
- Saved predictions/telemetry canonical hashes match each other and the unchanged fixed dataset.
  Staged-file ownership and local-credential screening passed; no credential values were printed.

The full suite emitted 17 existing Alembic `path_separator` deprecation warnings. All checks
passed; no shared Alembic configuration was edited. The disposable test containers/network were
removed after verification; application databases and named volumes were preserved. The XML is
retained locally in ignored `.pytest_cache/formation/apodex-linux-suite.xml`.

## Remaining quality and integration gates

O3 remains incomplete: Apodex has not demonstrated reliable completion of the tuning set, and
Pranit must independently review labels and actual outputs, approve the baseline and agree quality
targets before tuning and a sequential fixed-holdout evaluation. Condition-key conventions and
paraphrase duplicate handling remain team decisions. The human review packet/convention proposal
in [draft PR #23](https://github.com/Pranit-DC/ContextBridge/pull/23) is still pending; this change
reuses its safe telemetry fixes without merging that branch or claiming review approval.

The runner's OS lease coordinates one checkout only. Production BYOK secret handling, account-wide
rate/concurrency control, worker retry/cancellation and provider injection remain with Pranit;
requirements are in [integration requests](../../docs/formation/integration-request.md).
No shared contracts, persistence, dependencies, Compose, CI or other member's files were changed.
All PR and branch merges remain manual with the user.
