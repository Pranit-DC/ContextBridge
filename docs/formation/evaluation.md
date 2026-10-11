# O3 dataset preparation and offline scoring

The original deliverable prepared synthetic inputs and offline scoring without model calls.
The user subsequently authorized verification of their configured free OpenRouter model.
See the [actual live report](../../evaluation/formation/openrouter-live-report.md): the initial probe
failed reliability checks and does not complete O3. No private transcript was submitted.
The subsequent [Gemma availability attempt](../../evaluation/formation/gemma-baseline-report.md)
also failed. Pranit subsequently accepted the 24 dataset labels and seven output judgements,
and endorsed the proposed conventions from his side in the
[formal review](https://github.com/Pranit-DC/ContextBridge/pull/23#pullrequestreview-5484764979).
These were agent-assisted annotations accepted by Pranit, not labels independently authored
without assistance. Om/Harshal agreement, a reliable baseline, production quality and targets
remain pending. See the [reconciliation report](../../evaluation/formation/o3-review-reconciliation-report.md).

## Fixed inputs

`evaluation/formation/tuning.json` and `holdout.json` each contain 12 synthetic cases and 10
expected atomic claims covering FACT, DECISION, PREFERENCE, STATE, EVENT and LESSON. Cases exercise
decisions, developer scope, dates, conditions, identifiers/units, negation, rare lessons, adoption,
assistant guesses, filler, hypothetical plans and ambiguous applicability. Events have explicit
binding and stable IDs. Expected claims cite actual excerpts in their synthetic user/tool messages.

Pranit accepted these design labels; the original dataset metadata and hashes remain unchanged.
Acceptance does not establish production accuracy or all-team agreement. Tuning is
for later prompt/configuration work. Keep holdout fixed for the approved baseline, and never tune
prompts/thresholds from its results. Public files are not secret and cannot guarantee absence from
a future model's training data. O2's visible regression cases are separate from these splits.

`manifest.json` records revision, counts and canonical SHA256 fingerprints. Canonical JSON uses
validated models, sorted keys, compact separators and UTF-8, so key order and Windows newlines
do not change identity. Content/label changes invalidate existing run/review artifacts. Review
changed labels from evidence and document a new revision, rather than changing answers to fit
predictions. Provider, baseline and agreed targets remain null.

## Run without a provider

```text
uv run python scripts/formation/evaluate.py --split tuning --self-check
uv run python scripts/formation/evaluate.py --split holdout --self-check
uv run python scripts/formation/run_checks.py
```

Self-check constructs recorded proposals from expected claims and exercises the existing
Extractor/AdmissionPolicy with recorded support labels. Labels and outputs share their source by
design: this is a fixture/schema/policy check, never a model measurement. Reports say
`recorded_fixture_counts`, `model_executed_by_runner: false`, and `quality_gate: pending`.
No synthetic proposal is sent to the database or treated as a real project fact.

## Saved prediction and review artifacts

```text
uv run python scripts/formation/evaluate.py --split tuning --run RUN.json --annotations REVIEW.json
```

Private evaluation schemas live in `scripts/formation/evaluate.py`; they are not new shared V1
contracts. Run fields are `schema_version`, `mode`, `split`, `dataset_sha256`, `metadata` and `cases`.
Mode is `recorded_fixture` or `model_predictions`. Each case supplies `case_id`, untrusted
`proposals` (complete Candidate dictionaries), `decisions` (AdmissionDecision dictionaries),
nullable safe `error_code`, `latency_ms`, `input_tokens`, `output_tokens` and `cost`.

Metadata records provider ID, model ID, prompt version, aware recording time, bounded non-secret
configuration and optional USD/INR cost currency. Model-prediction artifacts require non-null model,
prompt and recording metadata. Never put credentials/private base URLs in artifacts. Missing
observations use null, not invented zeroes. Capture structurally valid proposals before semantic
rejection to measure unsupported generation; represent malformed/refusal/timeout output with safe
failure metadata without storing rejected raw text. The bounded free-model exporter below now uses
the actual injected adapters; production quality and approved provider wiring remain pending.

Review fields are `schema_version`, `label_source`, `dataset_sha256`, `run_sha256` and `cases`.
Each candidate needs one judgement: candidate ID, nullable matched claim ID, support
(`supported`, `unsupported`, `uncertain`), expected admission and evidence-based rationale.
Model predictions require `human_reviewed` labels; fixtures require `recorded_fixture`. Review
source and meaning, including qualifiers, dates and adoption; claim-key/keyword equality is
insufficient. Paraphrases can match through independent annotation; the scorer never invents
semantic matches. Expected type, conditions/time and genuine provenance must still agree.

Review is bound to the exact canonical run hash. Changed predictions, missing/duplicate cases,
unknown/missing labels and a different split/dataset fail safely. Candidate IDs are unique across
the run. Failed batches cannot also claim successful admission. Inputs are bounded at 10 MB
before decoding; invalid JSON, duplicate keys, non-finite values and recognized secrets fail with
`INVALID_INPUT`. Reports omit raw claims, evidence, rationales and exceptions.

## Counts and rates

| Measurement | Definition |
| --- | --- |
| Useful-claim precision | Unique matched expected claims / proposed candidates |
| Useful-claim recall | Unique matched expected claims / expected claims |
| Unsupported-claim rate | Independently labelled unsupported proposals / proposals |
| Uncertain-claim rate | Independently labelled uncertain proposals / proposals |
| Admission error rate | Decisions differing from independent expectations / present decisions |
| Failures/missing decisions | Separate counts; never disguised as correct empty output |
| Cases with an error code | `cases_with_error_code`; includes blocked cases |
| Legacy failure count | `failed_cases` is a compatibility alias for cases with an error code |
| Scope/provenance errors | Separate structural counts even when aggregate rates look good |

An expected claim counts once; duplicate predictions cannot inflate recall and reduce precision.
A duplicate memory remains useful extraction but expects admission REJECT in its comparison
context. Empty denominators yield null, not perfect scores. Telemetry reports known/missing case
counts; totals remain null when any observation is absent. Test runtime is not model inference
latency, and missing provider cost is not a claim of zero cost.

All expected claims contribute to recall, including those in unattempted cases. Removing blocked
cases would inflate the sequential Apodex run from its actual 1/10 recall. The legacy
`failed_cases=10` does not mean ten failed model executions: it includes nine blocked cases.

## Validate execution evidence offline

Supply the sidecar explicitly; scoring never discovers one automatically or executes a provider:

```text
uv run python -m scripts.formation.review --split tuning --run evaluation/formation/apodex-tuning-sequential-20261012.json --review evaluation/formation/pranit-reviewed-20261012/apodex-tuning-sequential-20261012.review-completed.json --telemetry evaluation/formation/apodex-tuning-sequential-20261012.telemetry.json
uv run python -m scripts.formation.evaluate --split tuning --run RUN.json --annotations ANNOTATIONS.json --telemetry RUN.telemetry.json
```

The private schema in `scripts/formation/execution.py` verifies canonical dataset/run hashes,
prompt and requested-model identity, complete unique known case IDs, ordered call indices/stages,
call counts, stop/budget conditions and consistent latency/usage/cost/error observations. Unknown
fields, malformed numbers, duplicate or unknown IDs, inconsistent records and mismatched inputs
fail safely with `INVALID_INPUT`. No credentials or database access are required.

`execution.case_counts` separates completed network cases, attempted failed network cases,
unattempted cases, local-only cases and unknown cases. `provider_stop_cases` and `call_budget_cases`
are subsets of unattempted cases. Sequential Apodex has 1 completed, 1 attempted failure, 9
provider-stop cases and 1 local-only case, across three recorded HTTP calls. This is saved execution
evidence, not proof that the failed HTTP attempt completed model inference.

Without a sidecar, execution is unknown for every case. Legacy call-only sidecars identify recorded
attempts but leave missing case execution unknown. Gemma's sidecar therefore reports 11 attempted
failures and 1 unknown case; its historical report identifies the assistant case from separate
runner/source evidence. The scorer does not infer that local-only status from a missing call.
Hash/consistency validation does not independently authenticate network execution or reviewer
identity. Observed model, tokens and cost remain null when absent; dataset/run JSON is unchanged.

Saved-artifact scoring does not execute or authenticate a model run. It produces annotated counts
while the quality gate stays pending. A real O3 baseline still needs approved provider/verifier
execution, reviewed labels, recorded configuration/prompt/latency/tokens/cost and agreed targets
after the baseline, before tuning. Persistence/conflict mutation and engine wiring remain Pranit's
responsibility; consolidation remains O4.

Recorded preparation checks: [O3 dataset report](../../evaluation/formation/o3-preparation-report.md).

## Authorized free-model verification

`scripts/formation/verify_free.py` executes only the fixed synthetic dataset. It requires `--execute`,
hosted execution enabled, OpenRouter free-only routing, paid execution disabled and data collection
denied. It bounds calls per split (default 24, configurable 1–40), performs no automatic retries,
and refuses to overwrite existing artifacts. Extraction and verification share one request gate;
one request completes before the next starts. Starts are spaced by at least 3.1 seconds, configurable
with `--request-interval` from 3.1 to 60 seconds. Increase spacing for a lower provider quota.
A checkout-wide OS lease rejects a second live CLI run, even with another split/output path;
the OS releases the lease on exit or crash. It does not coordinate other checkouts or production
workers. On any `PROVIDER_UNAVAILABLE` error, later network attempts stop; the runner never
automatically retries or changes model, privacy or payment settings. Example after explicit approval:

```text
uv run python -m scripts.formation.verify_free --split tuning --output evaluation/formation/new-tuning-run.json --execute --max-calls 22
```

Run holdout separately only after independent review and target approval; never tune from it.
The initial authorized probe used process-only `ALLOW_HOSTED=true` and `RESPONSE_FORMAT=json_object`
overrides and preserved `.env`. One semantic verifier call is reused for the identical candidate/event
during extraction and admission, keeping the call budget bounded. It is not an independent reviewer.
Failed batches retain only validated, source-bound untrusted proposals and safe codes; malformed
raw responses are discarded. No memory is stored. Missing usage/cost observations remain null.
Each run exports a `.telemetry.json` sidecar bound to its canonical run/dataset hashes. It records
requested and observed models, HTTP status when available, individual call latency/usage/cost,
execution settings, and per-case `attempted`, `provider_stop`, `call_budget` or `local_only` status.
Cases blocked before a call have null usage/cost/latency, not fabricated inference results.
Call latency excludes pacing; case latency includes pacing and both processing stages.
Safe usage is retained from readable envelopes even when candidate content is invalid/refused;
an HTTP failure's body is discarded, so its unknown usage/cost remain null.
Exit status 0 means the artifact was exported, not that model quality passed. Every new run still
needs reviewed annotations; the quality gate remains pending for the saved accepted runs.

The user selected Apodex on 12 October 2026. Its evaluation profile uses
`apodex/apodex-1.1-mini:free` for extraction and verification and `json_object` with the unchanged
trusted wire schema and local strict validation. See the [test matrix](apodex-test-plan.md).
The synthetic tuning/holdout labels, fingerprints, prompt version and common contracts stay fixed.

## Prepare independent review without inventing labels

```text
uv run python -m scripts.formation.review --split tuning --run RUN.json --prepare --output NEW_REVIEW.json --telemetry RUN.telemetry.json
uv run python -m scripts.formation.review --split tuning --run RUN.json --review COMPLETED_REVIEW.json --telemetry RUN.telemetry.json
```

Preparation emits a blank JSON and companion Markdown showing actual evidence, comparison context,
design labels and untrusted predictions. It makes no model/database calls and refuses overwrite.
For each new review, Pranit must approve/reject the gold labels for every case, including zero-output
cases, then supply per-proposal semantic matches/support/admission expectations and rationales.
Completed reviews require reviewer identity/time and external review evidence, and are bound to
the exact dataset/run hashes. The local scorer validates completeness but cannot authenticate the
human's identity or independence; verify the review reference through the team's human process.
Blank, partial, disputed-label or changed-run reviews fail safely rather than produce quality scores.
Targets and production integration remain separate gates. See [Pranit's review request](o3-review-request.md).
The original blank packets remain unchanged. The four separately completed packets accepted by
Pranit are copied with immutable provenance in
[`pranit-reviewed-20261012`](../../evaluation/formation/pranit-reviewed-20261012/source.json).
