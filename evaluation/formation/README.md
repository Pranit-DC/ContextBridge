# Formation evaluation inputs

The user selected Apodex for continued O3 evaluation on 12 October 2026. Its
[test plan](../../docs/formation/apodex-test-plan.md) covers all 24 unchanged semantic scenarios
with protocol fixtures and adds paced, serialized live execution with explicit quota/failure stops.
The [actual sequential report](apodex-sequential-report.md) distinguishes three real calls from
unexecuted cases and fixture checks. Pranit accepted the annotations and endorsed conventions
from his side; O3 production quality and remaining team agreement remain pending.

O4 adds eight synthetic design-labelled scenarios in `consolidation-cases.json`. Run
`uv run python scripts/formation/demo_consolidation.py` without credentials or a database.
These checks validate policy, source preservation and provider boundaries; they do not measure
model accuracy. Independent labels, real semantic consolidation providers and team approval
remain pending. See [O4 validation](o4-report.md) and
[consolidation behavior](../../docs/formation/consolidation.md).

O3 preparation adds separate [tuning](tuning.json) and [holdout](holdout.json) datasets, each with
12 synthetic cases and 10 expected claims. The [manifest](manifest.json) fixes revision/fingerprints.
After preparation, the user authorized a synthetic-only check of their configured free OpenRouter
model. The [live verification report](openrouter-live-report.md) records actual failures and observed
telemetry. Pranit accepted the dataset labels/output judgements; an approved baseline and targets
remain pending.
See [offline scoring and annotation format](../../docs/formation/evaluation.md).
The original design-label metadata and hashes remain unchanged. Fixture runs do not measure model quality.

The follow-up [Gemma baseline report](gemma-baseline-report.md) records unavailable-provider
failures and null usage/cost rather than an accuracy claim. The user assigned Pranit as independent
reviewer. He accepted the Codex-assisted annotations and endorsed conventions from his side in
the [formal review](https://github.com/Pranit-DC/ContextBridge/pull/23#pullrequestreview-5484764979).
The [blank original packets](../../docs/formation/o3-review-request.md) are preserved;
separate [completed packets/provenance](pranit-reviewed-20261012/source.json) and corrected
offline score exports record that acceptance. [Proposed targets](o3-quality-targets-proposed.json),
Om/Harshal agreement and production quality remain pending.
Both dataset hashes remain unchanged. No new holdout evaluation or prompt tuning has occurred.

The [reconciliation report](o3-review-reconciliation-report.md) documents hash-validated execution
reporting. Offline `--telemetry` scoring separates attempted failures, unattempted cases,
local-only cases and unknown execution. All expected claims remain in recall; the Apodex
sequential run still matches 1/10. The compatibility `failed_cases` count means cases with an
error code, including blocked cases. Scoring needs no provider, credentials or database.

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
