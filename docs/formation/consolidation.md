# Consolidation proposals

The injected live interfaces now have Groq chat implementations: `ChatGroupingProvider` and
`ChatConsolidationVerifier`. See [120b implementation and synthetic execution](groq-120b.md).
Complete summaries remain extractive; these adapters do not own storage. The historical
fixture-stage notes below describe the initial O4 delivery. Fresh semantic quality and the
production shared factory remain subject to review/wiring.

`Consolidator(provider, verifier).propose(records)` accepts the unchanged V1 MemoryRecord
dictionary list and returns V1 ConsolidationProposal dictionaries. Import it from
`contextbridge.formation`. It proposes only; the module has no database, queue, separate store,
or default model. The shared engine authorizes reads, validates current sources and commits
derived STATE records and `derived_from` edges without rewriting source memories.

## Local policy and injected providers

The caller supplies authorized records belonging to one developer. V1 MemoryRecord has no
developer identifier, so Om cannot authenticate ownership from the supplied dictionaries.
Never give this module an unfiltered collection and rely on project grouping for authorization.

Before calling a provider, validate evidence, bounded content/conditions, explicit project or
developer scope, aware dates, current version numbers and ACTIVE/open validity. A future,
closed or superseded snapshot fails with VERSION_CONFLICT. Missing evidence, duplicate
memory/version IDs, assistant source kinds, malformed input or detected secrets fail with
INVALID_INPUT. Snapshot validation does not prove a source remains live in PostgreSQL.

Partition records by exact scope, project and condition dictionary before any provider sees
them. Exact conditions deliberately avoid inferring that different condition keys mean the
same thing; O3's convention approval remains pending. Contested buckets remain atomic.
Single records do not need consolidation. Frequency and confidence do not determine importance.

Inject `GroupingProvider.group(records) -> str`. It returns JSON such as:

```json
{"groups": [["44444444-4444-4444-8444-444444444444", "55555555-5555-4555-8555-555555555555"]]}
```

Every nonempty grouping must partition all supplied version IDs exactly once. No unknown,
overlapping or silently omitted sources are allowed. A singleton explicitly retains an
unrelated atomic fact. `{"groups": []}` abstains for that bucket. This local provider format
does not modify the common ConsolidationProposal contract.

Om constructs an extractive summary of complete source claims with their memory types.
Identical type/content pairs appear once, while every supporting version and deduplicated
source reference remains cited. No generated paraphrase or new fact is accepted at this stage.
Negation, filenames, units and rare details remain in the text. If the complete summary exceeds
8,000 characters, the group abstains; it never truncates a rare fact to fit. Proposal IDs are
deterministic for the exact source snapshots, renderer revision and summary, regardless of input
order. The engine's saved proposals and transactional replay remain the persistence guarantee.

Inject `ConsolidationVerifier.verify(proposal, records)` returning `supported`, `unsupported`,
or `uncertain`. It must check relatedness, support by actual user/tool evidence, compatible
meaning/time/conditions, rare details and unresolved contradictions. An evidence string proves
provenance only. The current recorded verifier contains exact synthetic design labels, not a
production semantic judge. Unknown labels return uncertain. There is no default verifier.

Unsupported or uncertain groups remain atomic and yield no summary. Same-key different text
also abstains conservatively; this does not declare a contradiction or choose a winner.
Different-key semantic conflicts still require the verifier. Successful empty output means
abstention, not evidence that every source was supported. Other independently supported groups
may be proposed. No conflict state, source content or stored version is mutated by this module.

## Bounds and failures

Input is at most 200 JSON records and 4,000,000 serialized characters. Existing 8,000-character
content/evidence and 20-condition limits apply. Grouping output is at most 32,000 characters;
the final batch is at most 20 proposals. Invalid JSON, extra/duplicate keys, nonfinite values,
forged/missing IDs, invalid verdicts and over-limit proposals fail safely with
INVALID_PROVIDER_OUTPUT. Timeout/connection failures raise retryable PROVIDER_UNAVAILABLE.
An exception fails the batch and cannot return partially accumulated proposals. Provider inputs
are copied to keep mutations from changing the resulting summary/provenance. Error messages
never contain source content or provider exception text. The shared secret detector is conservative
and non-exhaustive.

## Run and integration status

```text
uv run python scripts/formation/demo_consolidation.py
uv run pytest tests/formation/test_consolidation.py tests/formation/test_consolidation_examples.py
```

The runner uses eight synthetic design-labelled scenarios, including rare details, contradictory
claims, unadopted suggestions, ambiguous applicability and differing scope/conditions. It needs no
model, API key or database. Scenario counts are policy checks, not model quality measurements.
Independent semantic labels and actual O4 model grouping/verification remain pending.

`tests/formation/test_consolidation_integration.py` executes this actual Om module through the
merged ConsolidationService with real PostgreSQL and injected test providers. It checks
summary/source preservation, version edges, replay, abstention, updates/forgetting during both
provider stages and deletion of derived summaries. Existing formation write tests check repeat
ingestion and deferred extraction. Pranit's service re-reads sources after proposal generation and
before commit; a changed version rejects the job and a forgotten source cancels it. Om has no
commit/deletion fence of its own. In-flight provider inputs may exist until the call returns;
the module retains no source cache or saved proposal store.

The shared factory still needs approved real grouping and verification providers. Team review of
these handoffs and the O3 quality gate remain pending. No paid/private-data provider behavior,
common contract change or production wiring is selected here. See
[integration requests](integration-request.md) and [recorded validation](../../evaluation/formation/o4-report.md).
