# Apodex evaluation test plan

The user selected `apodex/apodex-1.1-mini:free` for O3 on 12 October 2026 and requested one
request at a time. Provider/model/key remain user configurable (BYOK). This profile uses OpenRouter,
JSON-object output with the existing trusted schema, free-only routing, no provider fallback,
`data_collection=deny`, and no paid/private-data execution. Do not weaken validation to fit a model.

## Fixed semantic scenarios

`tests/formation/test_apodex_profile.py` runs all 12 tuning and 12 holdout scenarios through a
mock HTTP transport using the exact Apodex profile. Generated fixture responses and recorded
verdicts validate protocol and policy; they are **not actual Apodex outputs or accuracy scores**.
No live holdout evaluation or prompt tuning is part of this change.

| Scenario | Required behavior / review |
| --- | --- |
| Explicit decision, fact, preference, state, event, lesson | Preserve type, useful atomic claim and real source binding; all six existing types are covered |
| Negation, filenames, numeric limits/units | Preserve meaning and exact values; human review must detect ambiguous unit conversion |
| Conditional claims and developer/project boundaries | Preserve conditions and scope; never infer applicability from another project |
| Dated events, state and effective time | Preserve established dates; uncertain time must not become an invented fact |
| Rare lessons | Retain useful one-off lessons when the recorded evidence supports them |
| Explicit adoption of an assistant suggestion | Cite actual user adoption; assistant-only claims produce no proposal and no network call |
| Filler and unclear scope | Return no guessed memory; missing authority/scope fails safely |
| Existing scoped duplicate | Extract supported content but reject admission against the injected ComparisonContext |

The original fixed dataset/manifest hashes and design labels stay unchanged. Pranit must independently
review real predictions and annotations, approve condition-key conventions and duplicate handling,
then approve a baseline and quality targets before tuning. Same-model verification is not independent
human review. Do not silently map `project_version` to `version`, adopt a paraphrase matcher, or
relabel missed duplicates. Those choices affect shared retrieval/resolution and need team agreement.

## Transport and low-quota cases

| Case | Expected result | Automated evidence |
| --- | --- | --- |
| Correct JSON-object response | Strict wire validation; request contains schema, selected model and privacy/zero-price constraints | Apodex fixed-case profile fixtures |
| Empty extraction result | Valid empty proposals; never substitute for a failed call | Fixed filler and assistant scenarios |
| Invalid schema, truncation, non-JSON, refusal, tool call, duplicate keys, non-finite values | Safe `INVALID_PROVIDER_OUTPUT`; no admission/persistence | Profile fixtures and `test_chat_provider.py` |
| Invented source, unknown message/event, wrong project, assistant evidence, duplicate condition keys | Fail before interpreting guessed content as a fact | `test_chat_provider.py` and formation evidence tests |
| Unsupported or uncertain semantic verdict | No successful admission; retain only screened proposals as untrusted review artifacts | Apodex verifier-disagreement fixtures |
| HTTP 400/401/402/403/404 | Sanitized unavailable failure; stop later network attempts; no automatic retry | Apodex HTTP status fixtures |
| HTTP 429/500/503 or timeout | Retryable unavailable classification; runner stops instead of consuming more quota | Profile status fixtures, transport timeout and gate-stop tests |
| Provider error body or exception includes secrets | Discard body/raw exception; expose safe code/status only | Transport and profile HTTP fixtures |
| Invalid output with safe reported usage | Retain actual observed model/tokens/cost; reject candidate interpretation | Profile malformed-content and telemetry tests |
| Missing usage/cost/model | Null values; never assume zero/free cost from missing observations | Transport/runner telemetry tests |
| Two stages attempt simultaneously | Shared gate serializes calls, including budget check; starts spaced by configured interval | Mock-only thread and injected-clock tests |
| Two live CLI processes in one checkout | Second lease fails before model execution; first survives; crash releases lease | Real subprocess lock test on Windows and Linux |
| Call budget exhausted | No further call; blocked cases explicitly labelled `call_budget` with null telemetry | Runner budget/export tests |
| Provider fails early | Later eligible cases labelled `provider_stop`; assistant-only case remains `local_only` | Runner stop tests |
| Existing output/sidecar, unsafe spacing | Reject before any call and preserve artifacts | Runner CLI tests |
| Actual database/Redis integration | Preserve engine-owned scope, versions, replay, forgetting and worker checks | Full repository suite on isolated PostgreSQL `_test` and Redis |

## Sequential live procedure

1. Check key quota without logging the key or raw response. Set a bounded call budget within
   remaining quota, allowing for one extraction plus one cached verification per candidate.
2. Use process-only Apodex model/verifier and `json_object` overrides; preserve `.env` and prompt v2.
3. Run tuning once with one request active, at least 3.1 seconds between starts, and no automatic
   retry. A provider failure stops remaining network work; report precisely what was unexecuted.
4. Export immutable predictions and hash-bound safe telemetry. Record observed model ID, call/case
   latency, available tokens/cost, invalid outputs and unavailable failures separately.
5. Pranit reviews evidence and annotations independently. Score extraction precision/recall,
   unsupported/uncertain rates and admission errors only after that review. Agree targets, tune
   against tuning only, then evaluate the fixed holdout sequentially.

Request spacing cannot guarantee shared free-provider capacity. OpenRouter documents both platform
and upstream causes of HTTP 429 in its [limits documentation](https://openrouter.ai/docs/api_reference/limits).
An unavailable request alone does not establish that the daily quota was exhausted.
The local runner lease does not provide an account-wide limiter across users/workers; that integration
belongs to Pranit and is recorded in [integration requests](integration-request.md).
