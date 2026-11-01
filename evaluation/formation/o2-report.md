# O2 recorded policy validation

Recorded on 11 October 2026 from `codex/om-o2-admission`, based on `develop` at
`a57b3153078ab1316464ee9c2b77e2702268df85` (merged O1 PR #12).
Environment: native Windows, Python 3.12.10, PostgreSQL 18 in the existing local Compose service.

| Check | Observed result |
| --- | --- |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed; 130 Python files formatted |
| Alembic upgrade and `alembic check` | Passed; no new upgrade operations detected |
| Full PostgreSQL pytest suite | 333 passed, zero skips, 45.97 seconds |
| Formation tests within that suite | 121 passed, including 9 PostgreSQL integration tests |
| Synthetic O2 labelled scenarios | 29 expected policy results reproduced |
| Overall code coverage | 96%; code execution coverage, not model quality |

The full run used `uv run python scripts/formation/run_checks.py`, which created a fresh local
database ending in `_test`, supplied both test database environment variables, ran required checks,
and checked pytest's XML for skipped tests. Migration downgrade/upgrade regression tests and actual
MCP subprocess tests ran as part of the suite. The test database remains available for inspection;
the configured application database was not tested/truncated. Nine existing Alembic
`path_separator` deprecation warnings remain in shared configuration; no shared file was edited.

## Observed policy behavior

The recorded scenarios reproduce admission/rejection/deferral for new decisions, useful rare
lessons, duplicates, filler, unsupported guesses, ambiguous source/scope/time and unavailable
verification. Low-usefulness supported filler rejects when confidence is also low. Duplicate
checks do not suppress records in another environment/project or with ended, superseded,
contested or later-recorded state. Scores at the configured threshold are eligible.

The PostgreSQL engine tests establish that formation proposals can reach the existing shared
engine without owning persistence. Recorded correction interpretation creates a new version and
preserves prior evidence. Recorded contradiction interpretation keeps both claims contested with
a `contradicts` edge. A backdated correction and a correction without an interpreter defer without
changing stored memory. Exact duplicate rejection adds no version. Different environments keep
separate records, and replay does not repeat mutations.

## Limits and next phase

The dataset is synthetic and visible to development. Its labels are design labels awaiting team
review, including injected support and relation verdicts. Passing cases show policy agreement and
actual database behavior under those fixed inputs. They do not establish real semantic extraction,
verification, comparison accuracy, confidence calibration or an unseen holdout result.

No real model ran. Model ID, prompt, token use, inference latency and provider cost are **not
measured**; the pytest duration is test runtime. Production event-reader/provider wiring remains
pending. O3 requires team selection of a real provider/verifier, tuning/holdout separation, a baseline
and agreed quality targets before tuning. O4 consolidation remains a separate future task.
