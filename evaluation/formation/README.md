# Formation evaluation inputs

O3 preparation adds separate [tuning](tuning.json) and [holdout](holdout.json) datasets, each with
12 synthetic cases and 10 expected claims. The [manifest](manifest.json) fixes revision/fingerprints.
After preparation, the user authorized a synthetic-only check of their configured free OpenRouter
model. The [live verification report](openrouter-live-report.md) records actual failures and observed
telemetry. Independent reviewed quality scores, an approved baseline and targets remain pending.
See [offline scoring and annotation format](../../docs/formation/evaluation.md).
Design labels await team review. Fixture runs do not measure model quality.

`admission-cases.json` is the O2 synthetic policy regression set. Its 29 design-labelled examples
cover useful memory, filler, duplicates, corrections, conflicting guesses, conditions/projects,
rare lessons, threshold boundaries, stale snapshots and uncertainty. All conversations, IDs and
evidence are synthetic. Labels await team review; no private transcript, credential, real model
run or accuracy claim is included.

## O2 dataset format

`templates` contains a contract-V1 event, candidate, comparison context and stored record.
Each named case patches these objects recursively. Arrays/scalars replace, including explicit
null; absent changes preserve the template. `record_patches` expands the record template into
the context's records; absence means none. `missing_event` simulates expired/deleted evidence.
`support` is an exact-pair recorded verdict (`supported`, `unsupported`, `uncertain`) or a simulated
unavailable verifier. It is a test label, not a real model's endorsement.

`expected` records outcome/reasons or an `error` for malformed input. `description` explains why.
`resolution_note` and optional `resolution_relation` are handoff labels for Pranit's tests; they
give admission no mutation authority. `thresholds` records the engineering configuration.
`schema_version` here identifies this fixture format; public module contracts remain V1.

Run `uv run python scripts/formation/check_admission.py` from the repository root. Its loader
expands complete examples and is reused in Om's tests. Reports omit raw evidence. Review source
and rationale before changing labels; do not merely copy a changed implementation result.

## Evaluation boundaries

This set is visible to development/tests. It is not an unseen holdout, a model benchmark or a
calibration study. Counts show recorded policy agreement. Coverage and recorded support labels
do not measure useful-claim precision/recall, unsupported-claim rates or real admission errors.

O3 needs separate tuning and fixed holdout inputs, an approved real provider/verifier, observed
model/prompt configuration, latency, token/cost data and measured errors. Agree targets after
recording the initial baseline and before tuning. No paid/private-data provider was selected.
