# Groq 120b implementation and actual synthetic evidence

Groq `openai/gpt-oss-120b` now implements the injected formation extraction, evidence verification,
optional semantic duplicate comparison, grouping and consolidation verification interfaces.
The user selected 120b for implementation; subsequent calls used only that model. Persistence,
conflict resolution, authorization and transactional source/forget fences remain in the shared engine.

The implementation is reviewable, but the production quality gate has **not passed**. The user
reported in-person approval of conventions, targets and new outputs. No completed per-candidate
judgements were supplied, so precision, recall, unsupported-claim rate and admission accuracy remain
unknown. No human judgements were generated or inferred from the verbal approval. The existing
Pranit review accepts the unchanged O3 gold labels and historical outputs, not these new judgements.

## Measured O3 executions

| Run | Completed network cases | Local-only | Actual calls | Proposals | Input/output tokens | Case p95 | HTTP-call p95 |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 120b v2 tuning baseline | 11 | 1 | 21 | 10 | 19,257 / 4,468 | 65.813 s | 2.437 s |
| 120b v3 tuning | 11 | 1 | 22 | 10 | 21,102 / 4,326 | 67.203 s | 2.152 s |
| 120b frozen v3 holdout | 12 | 0 | 23 | 11 | 22,560 / 4,676 | 65.993 s | 2.062 s |

These runs have zero attempted provider failures and zero unattempted cases. Every call reports
`openai/gpt-oss-120b`. Cost is unknown/null for every call. A confirmed free plan is operator
attestation, not an API-verified billing guarantee. Model availability and valid structured responses
do not establish semantic accuracy. Canonical dataset/run hashes and execution consistency were
validated offline using the sidecars before preparing review packets.

The approved case-completion p95 target is 30 seconds and **fails**. Case elapsed includes local
quota waits and processing; HTTP-stage latency is much shorter. The JSON report also records
remaining case elapsed after subtracting measured HTTP-stage time; that includes both quota waits
and local work, rather than a separately instrumented queue timer. Quantiles use inclusive linear
interpolation and are descriptive for this small dataset. Targets were not relaxed after failure.

The original baseline mistyped release state and rollback, used capture time for the rollback,
and admitted the paraphrased MariaDB duplicate. The v3 tuning observations correct those cases:
STATE, EVENT with explicit occurrence time, and REJECT/DUPLICATE through the injected comparison.
These are observable outputs awaiting completed human judgements, not a scored accuracy claim.

Prompt/configuration/targets and hashes were frozen before the holdout. Its original inputs and
outputs remain unchanged; it was not used for tuning. The fixed holdout has been used historically
and is not a fresh unseen benchmark. It exposes follow-ups for Om:

- The unknown repository, explicitly outside Aurora, still produced an admitted project-bound
  MySQL FACT against an empty gold label.
- Python V1, development ports and offline SQLite omit expected condition dictionaries.
- The Python runtime choice and adopted Memcached cache choice are emitted as FACT rather than
  the gold DECISION type; stable keys still vary for some other subjects.

Keep this frozen result visible. Further tuning needs a separate development iteration and a new
independently reviewed holdout; do not revise these labels or tune on this holdout to obtain a pass.
The saved proposals are untrusted evaluation evidence, never stored project memories.

## O4 evidence verification

Both O4 runs use the same eight fixed synthetic source scenarios, with six network cases and
two local-only boundary cases. Each makes nine sequential 120b calls, with no provider failures,
unattempted blocked cases or memory writes. Initial counts match seven of eight design labels:
the verifier incorrectly endorses the ambiguous-applicability group.

The O4 verifier was then tightened to assess every original `version.source.evidence` and its
authority/adoption, rather than trust an ACTIVE source claim. Its v2 retest matches all eight
design proposal counts and abstains for the ambiguous group. Input/output usage is 7,679 / 1,096
initially and 8,756 / 1,098 after the revision; all costs remain unknown. This is tuning-set count
agreement, **not human-reviewed semantic accuracy or a production quality pass**.

This later change affects the O4 evidence prompt only. The frozen O3 extraction, verification
and duplicate prompt hashes remain identical, and no O3 holdout result drove that change.
The original full-file freeze describes the completed O3 execution before this subsequent O4
revision; the JSON report identifies the later changed file and prompt version separately.
Separate O4 review packets include all source evidence, proposals, citations and blank judgements.

## Regression checks and ownership

The complete Linux all-extras suite passes **1,054 tests, zero failures/errors/skips**, including
476 formation tests, actual PostgreSQL/vector/viewer/MCP tests and all three real Redis prefork
probes. Five new database regressions use the actual shared engine with HTTP fixtures and confirm
commit behavior and rejection/cancellation when sources update or are forgotten in either provider
stage. Those HTTP fixtures test behavior, not real model quality. Native focused tests: 35 passed.

Ruff lint/format, migrations to `71e473f5df6d`, and `alembic check` passed against the isolated
`contextbridge_om_groq_test` database. The final full run after the O4 prompt revision also passed
all 1,054 tests in 129.10 seconds; its XML confirms zero skips before cleanup. The 17 existing
Alembic configuration warnings do not
represent skipped tests. No development database was truncated. Disposable infrastructure is
removed after the verified reports; the user's application remains healthy.

Initial restricted Windows attempts failed temporary/cache setup, then passed using the normal
runtime. A simulated-clock floating-point stall interrupted a first suite attempt; the fixture
clock was corrected to advance after positive sleeps and all tests were rerun. Neither issue is
misreported as model failure. No shared fixtures or runtime contracts were weakened.

Only Om-owned formation source/tests/scripts/docs/evaluation and Om's plan changed. Shared API,
models, migrations, MCP, Compose, CI and dependency manifests remain untouched. Both environment
files are preserved; credential/ownership screening precedes commit. Production provider/factory,
account-wide quota and scoped BYOK wiring remains assigned to Pranit in
[integration requests](../../docs/formation/integration-request.md). No merge is performed.

## Review and evidence

Machine-readable measurements: [implementation report](groq-120b-implementation-report-20261012.json).
Configuration: [frozen O3 inputs](groq-120b-v3-frozen-20261012.json),
[reported target approval](o3-quality-targets-approved-20261012.json).
Use [Groq instructions](../../docs/formation/groq-120b.md) for the offline scoring commands.

Pranit's current packets are [v3 tuning](groq-120b-tuning-v3-20261012.review-pending.md),
[frozen holdout](groq-120b-holdout-v3-20261012.review-pending.md) and
[O4 v2](groq-120b-consolidation-v2-20261012.review-pending.md).
Fill the corresponding JSON judgements with a review reference. Incomplete O3 packets still fail
scoring; changed hashes, missing labels or inconsistent execution records are rejected offline.

The earlier 20b attempt failed its first call with HTTP 400; its precise cause was not observed.
Qwen completed two cases, failed two attempted cases and left seven unattempted after a confirmed
HTTP 429; one assistant-only case remained local. These historical attempts predate the user's
120b-only instruction and are retained without further calls. They do not prove a quality ranking.
