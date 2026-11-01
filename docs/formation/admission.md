# O2 admission and comparison

`AdmissionPolicy(verifier, event_lookup, min_confidence=0.8, min_usefulness=0.6)` implements
`assess(candidate, ComparisonContext) -> AdmissionDecision` from contract V1. Both dependencies
are injected. The module has no memory store, database mutation or production provider default.

## Decision order

1. Validate complete Candidate/ComparisonContext shapes. Empty content, missing required fields,
   invalid scores and malformed scope fail with safe `INVALID_INPUT`, never a guessed proposal.
2. Reject recognized secrets in a candidate. Secret-bearing comparison input fails safely.
3. Defer a future snapshot or one preceding the proposed effective time: `AMBIGUOUS_TIME`.
4. Read the original authorized event. Missing evidence defers with `INSUFFICIENT_EVIDENCE`.
   Conflicting event/candidate bindings defer with `AMBIGUOUS_SCOPE`; no scope is inferred.
5. Reject unknown/assistant references, mismatched provenance and invented excerpts with
   `UNSUPPORTED_CLAIM`. The independent injected verifier checks semantic support, including
   type, conditions and time. Unsupported claims reject; uncertainty defers. Timeout/connection
   failures defer with `PROVIDER_UNAVAILABLE`; malformed output fails with `INVALID_PROVIDER_OUTPUT`.
6. For supported claims, reject scores below the usefulness gate with `LOW_USEFULNESS`.
   Then defer scores below the confidence gate with `INSUFFICIENT_EVIDENCE`. This rejects supported
   filler when both scores are low; evidence uncertainty is never overruled by scores.
7. Reject an eligible exact duplicate with `DUPLICATE`. Otherwise admit with existing safe reasons
   `REUSABLE_PROJECT_CONTEXT` and, for a user-sourced decision, `EXPLICIT_DECISION`.

No raw exception or rejected text appears in a result. The common contract has no decision for a
malformed Candidate, so empty content fails validation rather than manufacturing an ID for REJECT.
Empty extractor output remains the normal result for filler. No keyword rule establishes truth.

## Features and configuration

| Feature | Meaning and limitation |
| --- | --- |
| Evidence support | Verifier judgement against cited user/tool messages; a quote alone is insufficient |
| Confidence | Provider estimate of extraction/support reliability; not calibrated truth probability |
| Usefulness | Expected future reuse; independent of repetition count |
| Novelty | Exact duplicates only; paraphrases/contradictions need engine interpretation |
| Scope/conditions | Explicit event binding and exact project/type/condition comparison |
| Time/lifecycle | Effective applicability and visibility in the checked snapshot |
| Type | One of six agreed types; a single important LESSON can be useful |

Thresholds are finite numbers in `[0, 1]`; equality is eligible. Zero disables that score gate,
but cannot disable evidence, scope, time or secret checks. Booleans, strings, null, NaN and infinity
are invalid configuration. Defaults are engineering choices, not measured quality targets.
There is no occurrence-count minimum, freshness-weighted truth score or latest-wins policy.

## Exact duplicates

Stored scope, project, type, conditions and exact content must match. The record must be clear,
ACTIVE, and the memory's current version. Its effective interval must contain both the candidate's
effective time and `checked_at`; intervals are `[valid_from, valid_to)`. Creation/recording times
must not postdate the snapshot. Ended, superseded, contested and later-recorded versions cannot
suppress a proposal. Case, negation, units and identifiers are not normalized away.

Same text in another project or environment is independent context. Pranit supplies authorized
records and rechecks owner, scope, versions and deletion at commit. Admission neither authorizes
a caller nor proves a snapshot is still live.

## Comparison notes for Pranit

The [29 labelled scenarios](../../evaluation/formation/admission-cases.json) provide exact inputs
and `resolution_note` fields. Correction/disagreement cases also supply recorded
`resolution_relation` labels. These are synthetic design labels awaiting team review.

| Scenario | Admission | Shared-engine expectation |
| --- | --- | --- |
| New useful decision | ADMIT | CREATE after fresh checks |
| Exact eligible duplicate | REJECT/DUPLICATE | Keep existing version; no resolution/mutation needed |
| Explicit supported correction | ADMIT | UPDATE only after interpretation and expected-version checks |
| Unsupported conflicting guess | REJECT | No write or conflict edge |
| Supported disagreement | ADMIT | Interpret conflict; preserve evidence and avoid silent supersession |
| Different environments/projects | ADMIT | Separate scoped records; never update unrelated state |
| Backdated correction | ADMIT if supported | DEFER/AMBIGUOUS_TIME for out-of-order mutation |
| Missing/uncertain evidence | DEFER | No write or reinterpretation as success |
| Contested exact content | ADMIT | Do not clear contested state; default exact NOOP may retain it |

ADMIT does not name a target or propose UPDATE/LINK_CONFLICT. Semantic relation interpretation
and conflict mutation belong to the shared engine. Without an injected interpreter, the default
resolver defers a correction to an existing related decision.

## Reproduce

```text
uv run python scripts/formation/check_admission.py
uv run pytest tests/formation/test_admission.py tests/formation/test_admission_examples.py
uv run python scripts/formation/run_checks.py
```

The first command replays recorded labels without a database/model. It prints only case IDs,
expected/actual safe results and pass counts; any mismatch exits nonzero. The full runner creates
a fresh local `_test` database and runs every required repository check with zero skips required.
Engine tests cover duplicate rejection, corrections/history, conflict edges, backdated deferral,
absent interpretation, environment isolation and replay. Recorded results check policy/contracts
and actual database behavior, not real model quality.
