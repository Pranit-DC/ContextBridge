# Gemma O3 availability baseline and independent-review preparation

Recorded on 11 October 2026 on `codex/om-o3-gemma-quality`, created from latest `develop`
at `86d93e0` after the user manually merged PR #22. O3 remains incomplete. No merge was performed
by the coding agent, and no human review is represented as completed.

## Configuration and execution

The user selected `google/gemma-4-26b-a4b-it:free` for both extraction and verification in their
ignored local `.env`. The safe configuration check found an API key, `openrouter`, the official
HTTPS endpoint, JSON-object output, 30-second transport timeout and 8192 maximum output tokens.
Hosted execution was enabled; paid execution remained disabled, free-only routing enabled,
data collection denied, fallbacks disabled and prompt/completion/request price caps set to zero.
The existing `formation-chat-v2` prompt and strict local validation were retained without tuning.
The coding agent did not edit `.env` or `.env.mcp`.

The [official endpoint catalog](https://openrouter.ai/api/v1/models/google/gemma-4-26b-a4b-it:free/endpoints)
listed the explicit free model and JSON response-format support. Catalog capability is not proof
of working inference or semantic quality. The selected key authenticated against OpenRouter's
official key endpoint. A later quota check found remaining daily free requests, so that snapshot
does not establish daily quota exhaustion as the cause of these failures.

Executed once, without retries, on the fixed synthetic tuning dataset:

```text
uv run python -m scripts.formation.verify_free --split tuning --output evaluation/formation/gemma-tuning-baseline-20261011.json --execute --max-calls 32
```

No expected answers or ComparisonContext records were sent to extraction. Only original synthetic
events were submitted. The runner proposed no memory and has no database write path.

## Actual results

| Observation | Result |
| --- | --- |
| Dataset cases / expected design-labelled claims | 12 / 10 |
| Network cases / HTTP completion attempts | 11 / 11 |
| Failed network cases | 11 PROVIDER_UNAVAILABLE |
| Validated proposals / successful admission decisions | 0 / 0 |
| Assistant-only case | Returned empty locally, no network call |
| Median / maximum network-case elapsed time | 0.891 / 1.000 seconds |
| Sum of network-case elapsed times | 8.609 seconds |
| Calls with provider-reported model ID | 0; all unknown |
| Calls with known input/output tokens | 0; all unknown |
| Calls with known cost | 0; all unknown; total cost unknown |

These short failure latencies are not successful model inference times. Eleven HTTP attempts
do not prove eleven model inferences occurred. The requested model ID is recorded; no observed
model ID, usage or cost is fabricated for missing responses. No semantic precision, recall,
unsupported-claim or admission-accuracy score is claimed without reviewed labels. In particular,
the locally blocked assistant-only case is not a successful Gemma case, and unavailable-provider
failures are not correctly empty model responses.

Two additional minimal synthetic diagnostics returned HTTP 429. They did not expose or store
raw responses or credentials. Their sampled status supports a rate-limit diagnosis, but the
baseline runner did not retain per-request HTTP statuses, so it cannot assert each of the eleven
failures had that same status. The specific upstream/account/minute-limit cause remains unknown;
no Retry-After or reset time was available in the sampled responses.

A single synthetic tuning-case probe of the alternative explicit free
`liquid/lfm-2.5-2.6b:free` with JSON-schema output also returned PROVIDER_UNAVAILABLE, with no valid
proposal and unknown cost. It used process-only settings, the same deny/zero-price constraints,
one actual HTTP attempt and a maximum-two-call budget. It was not a full quality evaluation,
not selected as a default and not persisted as a successful model result.
Its [official model page](https://openrouter.ai/liquid/lfm-2.5-2.6b:free) warns of prompt/output
retention; the routing policy was not relaxed to admit a collecting endpoint. No private data
or paid call was used. Further retries/model shopping were stopped instead of exhausting the key.

## Provenance and telemetry

- [Immutable attempt artifact](gemma-tuning-baseline-20261011.json).
- [Per-call telemetry sidecar](gemma-tuning-baseline-20261011.telemetry.json), bound to the run hash.
- Canonical run SHA256: `7718489f496b86cf1544d4fbd561148e818384eef8f96cf88fbfdb4f723308c7`.
- Tuning dataset SHA256: `c98957503bea13f4b5c52741fd889f2dffdbd9b03576744327549e2103f6b192`.
- Holdout dataset SHA256: `ad6038dfd2f8f0b0ef625f40da9743e5519426ab7b61bfc23154d158ae32ac7f`.

The exporter now saves the requested and provider-reported model, case, extraction/verification
stage, safe transport code/retryability, elapsed time, tokens and available USD cost for each
HTTP attempt. Reused identical verifier verdicts cause no extra call. Unknowns remain null.
When a safely parsed envelope includes usage but its generated content is malformed/refused,
the transport now retains that real usage while still failing validation. Raw invalid content,
credentials and private data remain excluded. Transport success is separate from schema/semantic
success; a null per-call transport error is not a passed extraction/admission result.
Existing Run/dataset schemas and their historical canonical identities are unchanged.

## Review, convention and tuning gates

The user assigned Pranit to independent review and approval. Three offline packets now expose
the original evidence, contexts, design labels and untrusted predictions for the previous tuning,
previous holdout and current Gemma attempt. All human judgement and approval fields are blank.
See the [review request](../../docs/formation/o3-review-request.md) and
[proposed quality targets](o3-quality-targets-proposed.json).

The review request proposes canonical condition vocabulary and an injected, bounded semantic
duplicate comparison. These remain proposals, not agreed conventions or implemented policy.
No stored key is renamed, no common contract changes, and the shared engine retains persistence,
conflict and commit-time authorization/version ownership. Pranit and Harshal must agree consumer
condition keys. Pranit must review relation/admission semantics and the dataset labels.

No prompt/threshold tuning and no new Gemma holdout run occurred. A usable reviewed baseline and
approved targets must precede tuning; after tuning only on tuning cases, freeze the configuration
and prompt before the unchanged holdout evaluation. A reliable model has not yet been verified.
The earlier visible holdout remains a fixed evaluation split, not a guaranteed secret/unseen set.

## Regression validation

The focused provider/telemetry/review tests passed: **56 tests**. Whole-repository Ruff lint and
formatting passed on native Windows (222 Python files checked for formatting).
Using Docker Desktop Linux, Python 3.12.15 and locked all-extras dependencies, the complete
repository suite passed: **815 tests, zero skipped/failures/errors, in 78.81 seconds**.
This includes all three actual Redis/Celery prefork probes, the vector tests and all 15 viewer
AppTest cases. Seventeen existing Alembic path_separator deprecation warnings remain.
Fixture/mock-backed semantic tests establish code behavior, not actual model quality.

The fresh pgvector PostgreSQL 18 container used only `contextbridge_om_gemma_test`, synthetic
credentials and vector extension 0.8.7. Migrations to head and `alembic check` passed. Redis 7.4.6
was isolated with loopback broker database 15. Whole-repository Ruff passed inside the container
as well. Only selected source/test/docs files were copied; neither `.env` file was copied.
The JUnit report is preserved locally at `.pytest_cache/formation/gemma-linux-suite.xml` and
confirmed 815 tests with zero failures/errors/skips. The three verified disposable test
containers, their anonymous volumes and their isolated network were removed after checks.
The user's application database container and named volume were preserved.
