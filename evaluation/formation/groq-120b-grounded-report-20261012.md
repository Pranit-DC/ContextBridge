# Groq 120b source grounding, latency and review evidence

Prepared on `codex/om-formation-accuracy-latency` from `origin/develop` at `c784673`, after confirming
the user manually merged #27. Only Om-owned formation code/tests/scripts/docs/evaluation and plan
changed. No branch/PR merge was performed. All execution used synthetic inputs, sequential Groq
`openai/gpt-oss-120b` calls and the existing BYOK key. Both ignored environment files are unchanged.

The user requested all remaining Om implementation/evaluation preparation in one regular PR,
without waiting for Pranit's approval. The earlier in-person convention/target approval remains
recorded as user-reported provenance. It is not a substitute for candidate-level human decisions.

## Result and limitations

Compact source-grounded extraction, one batch audit, explicit project-exclusion/uncertainty
abstention, approved condition aliases and narrow duplicate/category/time rules are implemented.
Application entry points use injected providers and unchanged ComparisonContext. Reusable
`QuotaClient` keeps the local guard out of evaluation-only code; the engine owns all persistence.

New raw v4.3 tuning matched 8/10 expected claims under proposed judgements: status and dated
occurrence were labelled FACT, and the occurrence used capture time. The fresh v4.3 holdout
matched 9/10: it preserved category/conditions but still used capture time for the dated event.
Those candidates were admitted, giving proposed admission-error rates of 2/10 and 1/10.
Raw results remain visible and are not reported as passing quality targets.

The v4.4 source rules were derived from the v4.3 **tuning** status/event errors. Their prompts and
configuration were frozen before the separate two-case focused holdout. Corrected offline replays
of the broad tuning/holdout each match 10/10 with zero proposed admission errors; they are
metadata-only replays, not new live evaluations or independent evidence. They retain original
decisions, source text, evidence, scope and IDs, and never impute new tokens, latency or cost.

Two new focused live cases each matched their expected STATE/EVENT and explicit timestamp. The
occurrence needed one source-proved local type/time correction. Four actual HTTP calls succeeded;
this demonstrates the bounded integrated correction path, not perfect raw-model quality.
All new judgements are explicitly `agent_proposed`, `independent_review_complete=false`, and
`quality_gate=pending`. No human decisions or production quality pass were invented.

Previously accepted human decisions were also rescored offline, preserving their review
provenance. See [historical reviewed baselines](groq-120b-review-20261012/historical-reviewed-baselines.json).
Apodex still has recall 1/10 and the correct one-completed/one-failed/nine-unattempted/one-local
breakdown. New Groq numbers do not inherit that historical review.

## Measured latency and usage

See [hash-validated measurements](groq-120b-review-20261012/latency-and-usage.json).
Case-completion latency includes the runner's waits and local processing, not just HTTP time.
Null local-only latencies are excluded, never replaced by zero. P95 uses inclusive quantiles.

| Actual run | Network/local cases | HTTP calls | P95 / max case seconds | Input / output tokens |
| --- | --- | --- | --- | --- |
| Earlier v3 tuning | 11 / 1 | 22 | 67.20 / 67.28 | 21,102 / 4,326 |
| Earlier v3 holdout | 12 / 0 | 23 | 65.99 / 67.26 | 22,560 / 4,676 |
| New v4.3 tuning | 9 / 3 | 18 | 23.97 / 23.98 | 14,682 / 3,150 |
| New v4.3 fresh holdout | 9 / 3 | 18 | 23.81 / 24.08 | 14,710 / 3,132 |
| New v4.4 focused holdout | 2 / 0 | 4 | 20.92 / 21.14 | 3,220 / 612 |

The new measured runs meet the 30-second latency target for this workload. Different datasets,
fewer network cases and changed prompts mean this is an observed improvement, not a controlled
benchmark or production latency guarantee. Unknown pricing remains null; free-plan confirmation
does not verify request-level billing or data retention. No paid fallback/private data was used.

Compact prompts, lower output caps, batched verification and conservative observed-token estimates
reduce artificial reservation waits. Serial execution, the 61-second token window, call/token
budgets, process lease, unknown-usage retention and provider-failure stop remain enforced. Other
account activity/daily quota can still stop a run; production account-wide coordination is shared
work. See [implementation details](../../docs/formation/grounded-quality.md).

## Complete development history

All failed/intermediate evidence remains saved: v4, v4 retry, v4.1 and v4.2 tuning. The first v4 run
stopped after one audit returned HTTP 400/invalid_request_error: one completed network case, one
attempted failure, nine provider-blocked cases and one local assistant case. A later identical
synthetic audit diagnostic succeeded with HTTP 200. The exact HTTP 400 cause remains unknown;
no raw provider error, rejected generation or credential was retained, and no automatic retry ran.
Later development runs exposed atomicity, type and verification defects before the final freeze.

Fresh-v2 has 12 tuning and 12 distinct holdout source events covering all six memory categories,
version/environment/offline qualifiers, adopted suggestions, rare lessons, duplicates, explicitly
other-project/undecided messages and assistant-only input. Its held-out text/identities were frozen
before execution; original historical datasets are unchanged. Fresh-v3 reuses that tuning split
explicitly and adds only two new focused source events. These small synthetic sets do not establish
production accuracy or broad robustness to arbitrary wording.

Freeze records are [v4.3](groq-120b-v4.3-frozen-20261012.json) and
[v4.4](groq-120b-v4.4-frozen-20261012.json). After the v4.4 freeze, Ruff only reformatted two runner
statements; core source rules and prompt text were unchanged. Review/scoring/replay additions and
the final partial-failure telemetry guard do not change live requests. That guard omits correction
counts when a generation returns no validated proposals. Holdout results were not used to adjust
the frozen correction rules.

## Review and validation

[One-pass review packet](groq-120b-review-20261012/README.md) contains proposed decisions,
provisional scores and blank source/context/output packets for every case, including abstentions.
The scorer still rejects changed hashes, incomplete reviews, unapproved gold labels, malformed
execution evidence and unknown/duplicate case IDs. Failed/unattempted cases retain missed expected
claims in recall. Replay has its own mode and cannot reuse source execution telemetry as new calls.

Native focused checks: 53 passed, zero skips. The initial sandbox temporary-directory check failed;
rerunning with a workspace-owned temporary directory passed. Runner formatting was corrected and
Ruff lint/format checks passed. Dedicated Linux full-suite results are recorded in the final
validation entry below. Regression tests include full HTTP fixtures, metadata replay/hash guards,
unknown usage/budget/concurrency failures and actual shared-engine PostgreSQL no-write checks for
wrong project, omitted qualifiers and incorrect category. Fixture successes test behavior only.

Shared API/worker/viewer factory wiring, owner-authorized data access and account-wide quota/BYOK
configuration remain in [integration requests](../../docs/formation/integration-request.md), for
their assigned owner. No API/model/migration/MCP/Compose/CI/dependency/shared-test change is included.

Final Linux validation passed: **1,111 tests, zero failures/errors/skips**, including **533
formation tests**, actual PostgreSQL/vector/viewer/MCP checks and three Redis prefork probes.
The suite used `contextbridge_om_accuracy_test` with isolated Redis, never the user's development
database. `uv run ruff check .`, `uv run ruff format --check .`, migration upgrade to
`71e473f5df6d`, and `uv run alembic check` passed. Full-suite coverage was 91%; the 17 existing
Alembic warnings are reported rather than hidden. XML counts were independently checked.
The disposable test containers/anonymous data volumes/network were removed after verification;
the existing application database remains healthy. Ownership/actual-credential scans passed, and
the unrelated preexisting `package-lock.json` remains excluded from the PR.
