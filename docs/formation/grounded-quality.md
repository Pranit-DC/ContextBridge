# Grounded Groq quality and latency follow-up

This follow-up uses only Groq `openai/gpt-oss-120b`, the operator's BYOK key and synthetic inputs.
It follows the user's request to prepare all implementation, measurements and review material in
one regular PR without waiting for another approval. It does not manufacture human judgements.
See the [actual report](../../evaluation/formation/groq-120b-grounded-report-20261012.md).

The [13 October review fix](../../evaluation/formation/groq-120b-review-fix-20261013.md) supersedes
the original occurrence matcher: local category/time proof requires a finite positive assertion
in the complete cited source message. Speculative/negated forms and positive excerpts embedded
in uncertain reports cannot supply that proof or bypass a differing audit category. Unknown forms
fall back to semantic verification. Original outputs/freeze records remain historical evidence.
Use the [corrected rationale copies](../../evaluation/formation/groq-120b-review-corrected-20261013/README.md)
with the original pending human packets; their support/match/admission judgements and rates are unchanged.

## Injected application entry points

`GroundedProvider`, `BatchVerifier` and `BoundedDuplicateVerifier` live in
`contextbridge.formation.providers.grounded`. `QuotaClient` lives in `providers.bounded`; production
code need not import evaluation scripts. Existing Candidate, CapturedEvent, AdmissionDecision and
ComparisonContext contracts are unchanged. Pranit owns service/worker factory wiring.

Example composition with already authorized settings and event/record access:

```python
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.bounded import QuotaClient
from contextbridge.formation.providers.grounded import (
    BatchVerifier,
    BoundedDuplicateVerifier,
    GroundedProvider,
)
from contextbridge.formation.providers.quota import TokenGate

gate = TokenGate(smooth=True, max_total_tokens=50000)
calls = []  # Safe observations, never raw prompts, responses or credentials.
extraction = QuotaClient(
    settings.model_copy(update={"max_output_tokens": 1024}),
    calls=calls,
    gate=gate,
    max_calls=32,
    stage="extraction",
)
audit = QuotaClient(
    settings.model_copy(update={"max_output_tokens": 512}),
    calls=calls,
    gate=gate,
    max_calls=32,
    stage="verification",
)
comparison = QuotaClient(
    settings.model_copy(update={"max_output_tokens": 256}),
    calls=calls,
    gate=gate,
    max_calls=32,
    stage="comparison",
)
verifier = BatchVerifier(audit)
extractor = Extractor(GroundedProvider(extraction), verifier)
admission = AdmissionPolicy(
    verifier,
    authorized_event_lookup,
    duplicate_verifier=BoundedDuplicateVerifier(comparison),
)
```

The shared engine supplies authorized original events and fresh ComparisonContext records, owns
interpretation replay, persistence and conflict mutation, and rechecks versions/deletion before
committing. No provider or evaluator owns a memory store. Use one shared gate/call list per task;
account-wide coordination and per-user key handling belong to the shared application.

## Source checks and bounded corrections

The private compact wire schema omits metadata the model must not invent. Trusted event binding,
source metadata and IDs are reconstructed locally. Full original inputs are screened for secrets
before compacting, including fields omitted from the wire payload. Every claim needs an actual
non-assistant source message and a verbatim quote. No claim text is rewritten by corrections.

An explicit exclusion of the bound project abstains locally only when every non-assistant message
excludes it and contains no positive binding. Mixed-project conversations and similarly named
versions do not match that shortcut. A wholly speculative someday choice with explicitly no
selection/date also abstains. These narrow guards are not general semantic understanding.

One indexed audit verifies all claims from an event, checking support, bound/other/ambiguous scope,
category and exact conditions. All provenance is validated before that call. Missing, duplicate
or unknown indices fail safely. Verdicts are task-local hashes of complete event/candidate inputs;
changed content or source must be audited again. Uncertain evidence is not admitted as fact.

Approved condition aliases preserve explicit values; `project_version` maps to `version` and
conflicting aliases fail. Production/development/offline qualifiers are retained in atomic claims
and independently checked by the audit. Neither model's confidence nor schema success proves truth.

Complete positive, same-project literal assertions allow three bounded corrections:

- An explicit user primary-database adoption with the same value/key corrects FACT to DECISION.
- An unchanged quoted release/deployment/workflow status corrects its tag to STATE.
- An unchanged quoted completed occurrence with an explicit ISO timestamp corrects its tag to
  EVENT and copies that source time. Negated/speculative patterns do not match; future occurrence
  times fail. The audit still must support the claim and scope/conditions.

These are documented source conventions, not inferred replacements. Other wording uses semantic
verification. A complete positive primary-database paraphrase can reject a duplicate locally only
against an eligible clear/current/ACTIVE record with identical scope, type and conditions and the
same literal database value. Extra qualifiers/negation/uncertain records use the bounded model
comparison. Formation never chooses the winning version or mutates conflicts.

## Quota and failure behavior

The opt-in v4 profile uses compact prompts, one batch audit, smaller output ceilings, local
abstentions and literal duplicate comparison. A task-local numeric profile records only known
input-token observations for the exact model/endpoint/prompt/schema configuration. Subsequent
reservations add the entire new payload's UTF-8 bytes, output ceiling and framing margin to that
observed bound; unknown usage clears the estimate and retains the full reservation.

This remains a conservative estimate, not an exact tokenizer or billing guarantee. Smooth pacing
spreads calls using observed charges while retaining the rolling token window, shared call/token
budgets, serialization, process lease and stop after provider failure. No automatic retry, paid
fallback or evidence truncation is introduced. Provider/account limits remain authoritative;
other applications and daily account usage are not coordinated by this task-local guard.
See [Groq rate limits](https://console.groq.com/docs/rate-limits).

## Reproduction and one-pass review

The existing `.env` settings/key stay unchanged. The explicit execution flags attest synthetic
hosted/free-plan use for the process; they are not a provider billing verification.

```text
uv run python -m scripts.formation.verify_groq --model openai/gpt-oss-120b --profile v4 --dataset-revision fresh-v2 --split tuning --approved-conventions --execute --confirm-free-plan --output evaluation/formation/NEW-v4-tuning.json
uv run python -m scripts.formation.verify_groq --model openai/gpt-oss-120b --profile v4 --dataset-revision fresh-v3 --split holdout --approved-conventions --approved-holdout --max-calls 8 --max-total-tokens 12000 --execute --confirm-free-plan --output evaluation/formation/NEW-v4-focused.json
```

Saved evidence refuses overwrite. Both fresh corpora have canonical hashes. Freeze configuration
before holdout; do not use holdout feedback for tuning. Fresh-v3's tuning split explicitly reuses
fresh-v2 tuning; its two new holdout examples test only status/occurrence corrections.

Offline scoring/replay needs no key, provider call or database:

```text
uv run python -m scripts.formation.evaluate --split holdout --dataset-dir evaluation/formation/fresh-v2-20261012 --run evaluation/formation/groq-120b-v4.3-holdout-20261012.json --telemetry evaluation/formation/groq-120b-v4.3-holdout-20261012.telemetry.json --annotations evaluation/formation/groq-120b-review-20261012/groq-120b-v4.3-holdout-20261012.annotations-proposed.json
uv run python -m scripts.formation.replay_grounded --split holdout --dataset-dir evaluation/formation/fresh-v2-20261012 --run evaluation/formation/groq-120b-v4.3-holdout-20261012.json --telemetry evaluation/formation/groq-120b-v4.3-holdout-20261012.telemetry.json --output evaluation/formation/NEW-offline-replay.json
```

Replay validates the source execution hashes and changes only locally proved type/time metadata.
It preserves claim text, evidence, scope, IDs and original admission outcomes, including failures.
It does not rerun admission, create new network observations or demonstrate a new live holdout.
Replays use `mode=postprocess_replay`; their latency/tokens/cost remain null. Never bind a parent's
HTTP sidecar to a changed replay run hash.

[Review instructions](../../evaluation/formation/groq-120b-review-20261012/README.md) identify
the raw outputs, corrections, agent-proposed judgements and blank human packets. Pranit can review
everything in this PR. Agent-proposed scores explicitly keep `independent_review_complete=false`
and `quality_gate=pending`. Completed human packets still require case-label decisions, every
candidate judgement, source/run hashes and a review reference; incomplete packets remain rejected.
