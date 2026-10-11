# O3 dataset preparation and offline scoring

The original deliverable prepared synthetic inputs and offline scoring without model calls.
The user subsequently authorized verification of their configured free OpenRouter model.
See the [actual live report](../../evaluation/formation/openrouter-live-report.md): the initial probe
failed reliability checks and does not complete O3. No private transcript was submitted.

## Fixed inputs

`evaluation/formation/tuning.json` and `holdout.json` each contain 12 synthetic cases and 10
expected atomic claims covering FACT, DECISION, PREFERENCE, STATE, EVENT and LESSON. Cases exercise
decisions, developer scope, dates, conditions, identifiers/units, negation, rare lessons, adoption,
assistant guesses, filler, hypothetical plans and ambiguous applicability. Events have explicit
binding and stable IDs. Expected claims cite actual excerpts in their synthetic user/tool messages.

These are design labels awaiting team review, not independently human-validated truth. Tuning is
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
the actual injected adapters; independent human review and production wiring remain pending.

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
| Scope/provenance errors | Separate structural counts even when aggregate rates look good |

An expected claim counts once; duplicate predictions cannot inflate recall and reduce precision.
A duplicate memory remains useful extraction but expects admission REJECT in its comparison
context. Empty denominators yield null, not perfect scores. Telemetry reports known/missing case
counts; totals remain null when any observation is absent. Test runtime is not model inference
latency, and missing provider cost is not a claim of zero cost.

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
and refuses to overwrite existing artifacts. Example after explicit approval:

```text
uv run python -m scripts.formation.verify_free --split tuning --output evaluation/formation/new-tuning-run.json --execute --max-calls 22
```

Repeat with a distinct output path and `--split holdout` for a fixed baseline; never tune from it.
The initial authorized probe used process-only `ALLOW_HOSTED=true` and `RESPONSE_FORMAT=json_object`
overrides and preserved `.env`. One semantic verifier call is reused for the identical candidate/event
during extraction and admission, keeping the call budget bounded. It is not an independent reviewer.
Failed batches retain only validated, source-bound untrusted proposals and safe codes; malformed
raw responses are discarded. No memory is stored. Missing usage/cost observations remain null.
Exit status 0 means the artifact was exported, not that model quality passed. Independent annotations
and the quality gate remain pending even when the model returns structurally valid proposals.
