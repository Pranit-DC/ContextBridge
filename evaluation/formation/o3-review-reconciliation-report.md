# O3 review reconciliation and offline execution reporting

Prepared on 12 October 2026 for [PR #23](https://github.com/Pranit-DC/ContextBridge/pull/23),
targeting `develop`. The user explicitly authorized merging `origin/develop` at `f002076` into
the published `codex/om-o3-gemma-quality` branch. The PR remains for the user's manual merge.
No provider request, prompt tuning, new holdout run or database migration change is part of this fix.

## Reconciliation and review evidence

The runner, transport and their existing tests are identical to `origin/develop`, preserving
#25's serialization, pacing, shared call budget, provider-failure stop, OS process lock, safe
HTTP-status telemetry and execution sidecar. #23 retains the review CLI/tests, original blank
packets, immutable Gemma run/telemetry, convention proposals and proposed targets.

Pranit accepted all 24 dataset labels and seven output judgements and endorsed the conventions
from his side in the [formal review](https://github.com/Pranit-DC/ContextBridge/pull/23#pullrequestreview-5484764979).
These are Codex-assisted annotations explicitly accepted by Pranit; unaided independent
authorship is not claimed. Four completed packets are copied unchanged from commit
`bf3349003ac0bcadd42e1eedc8aa287a2072bb7d`, with immutable URLs/blob hashes in
[`source.json`](pranit-reviewed-20261012/source.json). The
[human acceptance record](https://github.com/Pranit-DC/ContextBridge/blob/bf1a68027a7271f325538c012dff45ed9121bd71/docs/reviews/formation/2026-10-12/human-approval.json)
establishes his acceptance externally; the offline scorer does not authenticate human identity.

Om/Harshal convention agreement, a usable baseline, approved quality targets and production
quality remain pending. Missed paraphrased duplicate admission, condition-key drift and the
uncertain unit qualifier remain quality follow-ups, not prerequisites for merging the scoped
review-tooling PR. The existing holdout has already been observed and is not an unseen set.

## Corrected saved-evidence scores

`failed_cases` remains a compatibility alias for `cases_with_error_code`. It counts every case
with an error code, including blocked cases, rather than failed model executions.
The explicit `--telemetry` input validates canonical dataset/run hashes and complete consistent
case/call records before execution reporting. It makes no network/database calls and needs no
credentials. No sidecar means execution unknown; a legacy call-only sidecar proves recorded
attempts but cannot establish the status of cases without calls. Saved consistency is not
independent authentication of network/model execution.

| Saved run | Completed network | Attempted failed network | Unattempted | Local-only | Unknown | Cases with error code | Matched / expected | Admission errors / decisions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Earlier Apodex tuning | 0 established | 0 established | 0 established | 0 established | 12 | 6 | 3/10 | 1/3 |
| Earlier Apodex holdout | 0 established | 0 established | 0 established | 0 established | 12 | 8 | 1/10 | 2/3 |
| Gemma tuning, legacy call sidecar | 0 | 11 | 0 established | 0 established | 1 | 11 | 0/10 | 0/0 (rate null) |
| Sequential Apodex, complete sidecar | 1 | 1 | 9 provider-stop | 1 | 0 | 10 | 1/10 | 0/1 |

The earlier Apodex runs have no execution sidecars. Unknown execution does not erase their
observed proposal/error artifacts or imply zero actual attempts. The historical Gemma report
identifies the assistant-only case using its runner/source evidence; the scorer conservatively
keeps it unknown because the saved legacy sidecar lacks a case-execution record.

Sequential Apodex has three recorded HTTP calls: extraction and verification for one completed
case, then one failed extraction attempt. Nine later network cases never started. Every missed
expected claim still contributes to overall recall, which remains **1/10 (0.1)**. A blocked case
cannot improve recall by being removed. Missing provider-reported model, usage and cost remain
unknown; whole-run usage/cost totals remain null. None of these results approves production quality.

Corrected offline exports using the accepted packets:

- [Earlier tuning score](pranit-reviewed-20261012/openrouter-tuning-live-20261011.score.json).
- [Earlier holdout score](pranit-reviewed-20261012/openrouter-holdout-live-20261011.score.json).
- [Gemma score](pranit-reviewed-20261012/gemma-tuning-baseline-20261011.score.json).
- [Sequential Apodex score](pranit-reviewed-20261012/apodex-tuning-sequential-20261012.score.json).

Reproduce the sequential score:

```text
uv run python -m scripts.formation.review --split tuning --run evaluation/formation/apodex-tuning-sequential-20261012.json --review evaluation/formation/pranit-reviewed-20261012/apodex-tuning-sequential-20261012.review-completed.json --telemetry evaluation/formation/apodex-tuning-sequential-20261012.telemetry.json
```

For the earlier runs, omit `--telemetry`; for Gemma, supply its legacy sidecar. All original
run/dataset identities and pending packets are preserved. See [CLI and schema documentation](../../docs/formation/evaluation.md).

## Regression validation

Native Windows focused execution/evaluation/review checks passed: **93 tests, zero skips**.
Whole-repository Ruff lint and formatting passed, with 236 Python files checked for formatting.
The regressions exercise the actual sequential breakdown, unchanged recall, missing historical
evidence, mismatched hashes, duplicate/unknown case IDs, malformed/inconsistent execution records,
HTTP/model/usage mismatch, unknown fields, invalid numbers, provider-stop/budget invariants and
incomplete/disputed/changed-run review rejection. A network guard rejects any provider call.
The tests validate code behavior against saved synthetic evidence; they do not measure new model quality.

Full Linux all-extras validation passed: **997 tests, zero skipped/failures/errors, in 178.58
seconds**, including **419 formation tests**, all three real Redis/Celery prefork probes, vector
checks, 15 viewer AppTest cases and actual MCP subprocess checks. Locked dependencies and Python
3.12.15 were used. Whole-repository Ruff lint/format checks passed inside the container as well.
Seventeen existing Alembic `path_separator` deprecation warnings remain in shared configuration.

The fresh pgvector PostgreSQL 18 container used only `contextbridge_om_review_test`, synthetic
credentials and vector extension 0.8.7. Migrations to `71e473f5df6d` and `alembic check` passed.
Redis 7.4.6 was isolated with loopback broker database 15. No `.env` file was copied. The local
JUnit report at `.pytest_cache/formation/review-linux-suite.xml` confirms all 997 tests ran with
zero failures/errors/skips; the complete checks container exited 0. The three verified disposable
containers, anonymous volumes and isolated network were removed after checks, preserving the
application database and its named volume.

Staged ownership/credential screening and `git diff --check` passed. Changes are confined to
Om's formation files and plan, and #25's runner/transport/tests remain identical to develop.
Passing recorded/mock-provider tests demonstrates behavior, not successful new model inference.
