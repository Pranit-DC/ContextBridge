# Formation contract boundary

This module proposes evidence-backed candidates, admission decisions and consolidation summaries.
It has no database, HTTP endpoint, queue, host hook, or production model default. The shared engine owns
authorization, persistence, conflict resolution, result replay, and deletion fencing.

## Configure your own provider

The opt-in formation adapter reads provider/model/key settings from the local `.env`; see
[user configuration](provider-configuration.md) for every setting, free OpenRouter routing,
local Ollama and Chat Completions-compatible endpoints. `scripts/formation/provider.py` validates
configuration without network calls by default. Explicit execution produces proposals only.
Shared API/worker/viewer wiring and real model quality evaluation remain pending.

## Run the recorded example

```text
uv run python scripts/formation/demo.py
uv run python scripts/formation/demo.py --duplicate
uv run pytest tests/formation
```

The first command loads the team's captured-event/candidate/admission fixtures and returns the
agreed candidate and ADMIT decision. The second supplies the stored retrieval fixture as an
in-memory ComparisonContext and returns REJECT/DUPLICATE. These are deterministic contract
checks with human-labelled synthetic examples, not measurements of model quality.

## Import and extraction

`import_transcript(messages, *, event_id, scope, project_id, agent, session, interaction,
occurred_at)` accepts one documented input format: a list of dictionaries containing exactly
`message_id`, `role`, and `content`. Roles are `user`, `assistant`, or `tool`. The caller supplies
explicit binding and stable event/message IDs. The helper returns a contract-V1 CapturedEvent
with `capture_method: manual_import`. It never invents project/session binding, silently truncates,
splits messages, or installs an agent hook. Reject oversized input and split it explicitly upstream.

`Extractor(provider, verifier).extract(event)` implements the shared dictionary entry point.
Inject a provider implementing `generate(event) -> str`: a JSON list of complete contract-V1
Candidate objects, including stable candidate IDs. Empty output `[]` means no useful candidates.
The provider must extract one reusable claim per candidate, preserve negation, filenames, units,
conditions, and supported effective dates, and avoid inventing scope or preferences.

Inject an independent `EvidenceVerifier.verify(candidate, event)` returning `supported`,
`unsupported`, or `uncertain`. It must check semantic support, atomicity, type, conditions, scope,
and time against the actual cited user/tool evidence. Matching an excerpt only establishes its
origin. The verifier must not endorse assistant suggestions, unadopted guesses, hypothetical
facts, filler, or ambiguous applicability. There is no default semantic verifier in O1.

The extractor checks event/provenance binding, known non-assistant references, matching source
kind, and a real verbatim excerpt before consulting the verifier. Unsupported/uncertain output
fails the batch rather than appearing as successful empty extraction. Invalid JSON, duplicate JSON
keys, non-finite/coerced numbers, duplicate candidate IDs, schema violations, secrets, or output exceeding
2,000,000 characters produce `INVALID_PROVIDER_OUTPUT`. Contract limits still bound candidates
to 100, content/evidence to 8,000 characters, events to 20 messages/32,000 content characters.
Timezone-aware dates become UTC; normalization does not rewrite the claim or its evidence.

Only user/tool messages can support durable claims. Assistant-only events return no candidates
without a provider call. Mixed transcripts retain assistant context but cannot cite it as evidence.
Common secret patterns are screened across all input fields before provider execution, and across
all output fields before returning proposals. This uses the project's existing non-exhaustive
detector. Input/schema errors return `INVALID_INPUT`; timeouts/connection failures return
retryable `PROVIDER_UNAVAILABLE`. Errors/logs do not include rejected text or provider exceptions.

## Admission handoff

`AdmissionPolicy(verifier, event_lookup, min_confidence=0.8, min_usefulness=0.6)
.assess(candidate, context)` implements the agreed dictionary entry point using ComparisonContext.
`event_lookup(event_id)` supplies the original authorized event from an injected engine/test reader;
this module stores nothing. Missing original evidence or uncertain semantic support yields DEFER.
Unsupported provenance/claims and secrets yield REJECT. An unavailable verifier yields DEFER.
Malformed candidate/context data fails safely with `INVALID_INPUT`.

Confidence is a provider estimate, not proof or a calibrated probability of truth. Usefulness is
estimated future reuse, not frequency. Both thresholds are configurable engineering defaults;
support checks precede score thresholds. Supported low-usefulness filler rejects even when
confidence is low. A useful lesson can be admitted after a single occurrence.
Context checked in the future or before the proposed effective time yields DEFER/AMBIGUOUS_TIME.

Exact duplicate rejection requires the same scope, project, type, conditions, and content, plus a
clear current ACTIVE version applicable at the candidate's effective time and snapshot check time,
created/recorded no later than that snapshot. Different environments,
projects, contested or stale versions do not constitute a global duplicate. This gate does not
perform semantic deduplication or decide which contradictory claim is correct. An admitted
correction remains a proposal; Pranit decides UPDATE/LINK_CONFLICT/DEFER against fresh state.

RecordedProvider is bound to an exact fixture event. RecordedEvidenceVerifier uses exact
event/candidate pairs with human labels; unknown pairs are uncertain. Both are test/demo
substitutes and must not be wired as production providers. Injecting arbitrary Python providers
is a trusted integration boundary, not a sandbox for malicious provider code.

## Status

O4's fixture-stage `Consolidator.propose(records)` is now prepared with injected grouping and
semantic-verification interfaces, complete source-text summaries, version provenance and shared-engine
PostgreSQL regressions. See [consolidation policy and usage](consolidation.md). Its recorded labels
are synthetic design fixtures; production provider wiring and semantic quality approval remain pending.

O1 merged in PR #12. O2 merged in PR #13; see
[admission behavior and engine notes](admission.md) and [fixture format](../../evaluation/formation/README.md).
O3's synthetic tuning/holdout datasets and offline scorer are prepared at the user's request;
see [evaluation workflow](evaluation.md). A user-configurable Chat Completions adapter and separate
verification calls are implemented locally; actual provider compatibility, execution and quality
measurements remain pending. Actual consolidation provider wiring and quality remain pending. PostgreSQL checks in
`tests/formation/test_engine_integration.py` exercise the newly merged P2 engine with recorded
formation providers; recorded database execution passed on native Windows/PostgreSQL 18.
No API, persistence,
common contract, dependency, or other member's module was changed. See
[integration requirements](integration-request.md).

For all required checks with a new dedicated database, start PostgreSQL at the local URL from
`.env`, then run `uv run python scripts/formation/run_checks.py`. The configured role must be
able to create databases. The runner creates a unique `contextbridge_om_*_test` database,
points migrations and the full pytest suite only at that database, and rejects skipped tests.
It displays no credentials and retains the test database for inspection. No test command targets
the application's configured database. For a configured `localhost` URL, the test runner uses
`127.0.0.1` to match Compose's IPv4 binding and avoid Windows IPv6 fallback delays; `.env` is unchanged.

## Recorded O1 validation

On 11 October 2026, native Windows/Python 3.12 and PostgreSQL 18 passed repository lint,
formatting, migration upgrade, `alembic check`, and all 286 tests with zero skips. This includes
the recorded formation-to-P2-engine checks for writes, replay, rejection, deferral and forgetting.
Both fixture demo modes passed. These results validate contracts and engine behavior with
recorded providers; they do not measure real model extraction or semantic-verification quality.

O2's full required run passed 333 tests with zero skips, including 121 formation tests, on the same
native Windows/PostgreSQL 18 environment. See the [O2 report](../../evaluation/formation/o2-report.md)
for commands, synthetic-label limitations and shared-engine comparison regressions.

The configurable provider's full required run passed 738 tests with zero skips, including
220 formation tests and the merged viewer's optional tests. See the
[configuration validation report](../../evaluation/formation/provider-configuration-report.md)
for credential/test-environment isolation and pending real-model measurements.
