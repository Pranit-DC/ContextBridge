# Actual free-model verification — 11 October 2026

The configured `apodex/apodex-1.1-mini:free` is **not recommended as a production formation default**
from this probe. Fourteen of 24 synthetic cases failed; the remaining responses also include a
condition-key mismatch and a missed duplicate. O3 quality approval remains pending.

## Authorization and configuration

The user explicitly requested verification after adding the documented settings and their key.
The key authenticated successfully through OpenRouter's current-key endpoint, without displaying
its value or account details. The live catalog listed the selected model with zero prompt/completion
prices and structured-output support. The actual Novita route nevertheless rejected `json_schema`
with HTTP 400, identifying `json_object` as its supported response format.

No private transcript was submitted and no paid model/fallback was selected. The agent preserved
`.env` and `.env.mcp`. For the authorized checks only, process configuration used:

| Setting | Actual value |
| --- | --- |
| Provider/requested extraction/verifier model | OpenRouter / `apodex/apodex-1.1-mini:free` |
| Endpoint | `https://openrouter.ai/api/v1` |
| Prompt | `formation-chat-v2` |
| Response format | `json_object` |
| Timeout / output limit | 30 seconds / 8192 tokens |
| Hosted / paid execution | Enabled for this probe / disabled |
| Free-only / data collection / provider fallback | Enabled / deny / disabled |

JSON-object mode initially lacked the full response contract and produced invalid output. The
formation adapter now supplies the trusted private JSON schema in its system prompt while retaining
all local strict validation. No shared V1 contract or fixture label was changed. Before the split
runs, one real smoke event returned a supported PostgreSQL decision in 26.765 seconds; its response
echoed the requested model ID, with 1144/3532 extraction input/output tokens and 686/586 verifier
tokens, both reporting zero cost. This is a compatibility check, not a general quality score.

## Fixed synthetic split results

Both dataset hashes are unchanged. The exporter sends the event only, never the expected answers
or comparison labels. The two splits ran concurrently, each sequential internally, capped at 22
model calls with no automatic retries. The same semantic verdict is reused only for an identical
candidate/event in extraction/admission. No model tuning followed holdout results.

| Observation | Tuning | Holdout | Combined |
| --- | ---: | ---: | ---: |
| Cases | 12 | 12 | 24 |
| Failed cases | 6 | 8 | 14 |
| `INVALID_PROVIDER_OUTPUT` | 2 | 5 | 7 |
| `PROVIDER_UNAVAILABLE` | 4 | 3 | 7 |
| Completed cases, including empty output | 6 | 4 | 10 |
| Validated proposals / admission decisions | 3 / 3 | 3 / 3 | 6 / 6 |
| Actual model completion calls | 14 | 15 | 29 |

One tuning case containing only an assistant message was blocked locally without a model call;
it is included in completed cases, not counted as successful model inference. Of 23 cases requiring
network calls, 9 completed with validated pipeline output. There were 20 design-labelled expected
claims across both splits. Six returned proposals do not establish six correct matches.

Across network cases, median end-to-end case latency was 12.766 seconds, mean 21.821 seconds, and
maximum 50.156 seconds. Successful network cases had a median of 10.218 seconds and range
1.110–24.860 seconds. These include verification/admission and concurrent provider contention.
The 30-second transport configuration did not produce a 30-second wall-clock bound: failures could
be returned later while waiting for a response/chunk. No throughput or hard-deadline guarantee is made.

Usage was available for 16 network cases: 22,500 input tokens, 25,998 output tokens and observed cost
USD 0. Usage/cost were missing for the other 7 network cases; complete totals remain unknown.
Rejected malformed raw responses were discarded, so their unsupported-claim rate cannot be measured.
The requested model ID is retained in split metadata; per-call response model IDs were not retained
in those artifacts. The successful smoke response ID above is the direct observed model evidence.

## Evidence review findings and limits

These are agent observations against synthetic source text and existing design labels, not
independent human-reviewed annotations or agreed accuracy metrics:

- `holdout-python-runtime` preserved Python 3.12 and the prohibition on 3.13, but used condition key
  `project_version` instead of the labelled `version`. Exact downstream filters could miss it.
- `tuning-duplicate` returned a MariaDB paraphrase and a new claim key. Actual admission was
  `ADMIT`; the fixed design label expected `REJECT`. Existing comparison is exact, so the shared
  engine's relation reasoning and a reviewed key convention remain necessary before persistence.
- `holdout-upload-limit` preserved 2097152 bytes but added "2 MB", an ambiguous conversion; the
  source supports the byte count. Review unit precision rather than accepting model confidence.
- No proposals/decisions were returned from the failed batches. Invalid output and unavailable
  providers were kept distinct from genuine empty extraction. No memory was saved.

The scorer requires independent `human_reviewed` labels for model predictions. No such annotations
were fabricated, and useful-claim precision/recall, unsupported-claim rate and formal admission-error
rate remain unreported. Review labels and select a reliable configuration before agreeing targets.
Consolidation, production provider assembly and real integrated model quality remain pending.

## Saved artifacts and reproduction

- [Tuning run](openrouter-tuning-live-20261011.json): canonical run SHA256
  `c8fc78c550be4b08ea4da4dd9a5d061476d385cba05a954f620f20dfc7a9f223`.
- [Holdout run](openrouter-holdout-live-20261011.json): canonical run SHA256
  `5f98321ab90852c1e163f89ab46a2af2a3ef60bdb62b78ca684046755cc6ba19`.
- Dataset SHA256: tuning `c98957503bea13f4b5c52741fd889f2dffdbd9b03576744327549e2103f6b192`;
  holdout `ad6038dfd2f8f0b0ef625f40da9743e5519426ab7b61bfc23154d158ae32ac7f`.

The dataset manifest retains the original preparation metadata; the subsequent authorization and
actual runs are recorded here. See [workflow](../../docs/formation/evaluation.md#authorized-free-model-verification)
for `python -m scripts.formation.verify_free`, explicit execution consent and unique output paths.
An export's exit status is not a passing quality gate. Existing run files cannot be overwritten.

## Repository verification, separate from model quality

The feature branch was rebased onto latest `develop` `23365b6` without a merge. Changes remain
within Om's formation files and plan. The compatibility fix and bounded runner have six new
regression cases covering schema delivery, output validation, call budgets, exact verdict reuse,
unsupported-output capture and preservation of earlier runs.

Native Windows: Ruff lint and formatting (215 Python files), dedicated PostgreSQL migration upgrade
and Alembic drift checks passed. Pytest passed 801 tests, with 3 explicitly Linux-only prefork worker
tests skipped. That run was rejected as incomplete by the zero-skip check runner.

Docker Desktop Linux: the existing project Dockerfile, frozen lock and all extras were used with
isolated PostgreSQL 18/pgvector and Redis containers. The dedicated database was
`contextbridge_om_linux_test`; only isolated Redis database 15 entered the transport probes.
Ruff, formatting, migrations and Alembic drift checks passed. The **complete 804-test suite passed
with zero skips**, including all real prefork crash/retry/broker probes and 15 viewer AppTest cases.
Both platforms reported 17 existing Alembic `path_separator` deprecation warnings. No shared
Compose, Dockerfile, CI, model, migration, dependency or other member's test was edited.

Application memory/database credentials were never supplied to the Linux probes. They used synthetic
test credentials. The native test database was freshly created as `contextbridge_om_b28bb0d3ba10_test`.
These regression checks exercise storage/workers/protocols using recorded providers; their passing
results are separate from the real model's failures above. The PR remains for manual review/merge.
