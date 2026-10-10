# Harshal — retrieval, inspection viewer, and evaluation

Your outcome: retrieve the right memory with clear evidence and uncertainty, and give users a
simple viewer to inspect, correct, and forget it. Demonstrate the product with measured results.

Read [common contracts](contracts-v1.md) and [team workflow](README.md). You can start retrieval
with an in-memory repository and the viewer with a fake API, without waiting for new DB tables.

## Your files and boundaries

You own new `src/contextbridge/retrieval/`, `src/contextbridge/inspection/`,
`tests/retrieval/`, `tests/inspection/`, `scripts/retrieval/`, `docs/retrieval/`,
`docs/inspection/`, `evaluation/retrieval/`, `evaluation/end_to_end/`, and this plan.

Do not edit shared API/models/schemas/migrations, MCP adapters, Compose, CI, root tests,
`pyproject.toml`, or `uv.lock`. Your retrieval module reads through Pranit's repository interface;
the viewer calls HTTP, never SQL directly. Add local test helpers under your own directories.
Put shared needs in `docs/retrieval/integration-request.md` or the inspection equivalent.

## Start now without waiting

Create `feat/harshal-retrieval-contract` from latest `develop` using the [branch steps](README.md).
Implement `Retriever.search(query, repository, embedder, verifier)` with a fake repository loaded
from [retrieval-snapshot.json](fixtures/retrieval-snapshot.json). Use a fake embedder and verifier.
Return the agreed [retrieval-result.json](fixtures/retrieval-result.json) shape.
Create `ViewerClient` using today's httpx and fake HTTP responses. A UI library can be added by
Pranit later; client behavior and viewer view-model tests can start immediately.

## H1 — retrieval policy and compact cards

Deliver:

- Query normalization that preserves explicit project, conditions, time, identifiers, and limits.
  Do not guess dates/environments and override the caller's actual filters.
- Merge lexical, semantic, and symbolic ranked matches. Start with reciprocal rank fusion:
  combine each channel's rank rather than pretending their raw scores share one scale.
  Keep fusion parameters configurable and evaluate them later.
- Version-ID deduplication, deterministic ties, applicability checks, bounded candidate counts,
  and compact cards with source references and contested status.
- Default 3 cards with optional bounded expansion, never more than the caller/MCP limit.
  Empty results and degraded semantic availability must be visible, not filled with guesses.

Acceptance: no duplicate card; explicit scope/condition/time filters survive all stages; a
historical query can use the correct historical version; unrelated projects are excluded;
an unresolved conflict stays labelled; query limits and stable order hold under tied scores.
Fakes must include out-of-scope/invalid records to exercise your defensive checks.

## H2 — real embeddings, evidence verification, and graph expansion

Deliver:

- `EmbeddingProvider.embed(texts)` with model/dimension metadata, finite-vector validation,
  batching, bounded calls, and a fake provider. Choose a real local embedding model with the team
  based on language, RAM, download size, license, and measured retrieval quality.
- Lexical fallback on embedding failure, without claiming semantic retrieval succeeded.
  Give Pranit vector dimensions/index requirements; he owns pgvector and SQL integration.
- A selective verifier checking inspected source evidence, returning supported/uncertain.
  Do not equate word overlap, a high vector score, or model confidence with proven truth.
- Bounded graph expansion over same-scope valid relationships; avoid cycles and scope leaks.
  Recheck live state before cards return; deleted/stale entries must not appear.

Acceptance: a semantic paraphrase retrieves a relevant labelled memory with the real embedder;
exact file/function identifiers remain findable lexically; mismatched models/dimensions fail safely;
provider timeout degrades clearly. Contradictory/insufficient evidence returns uncertainty.
Graph cycles stop, every hop respects filters, and stale-index records are removed.

## H3 — inspection viewer, working against today's API first

Deliver:

- A small Streamlit viewer with service URL/token configuration kept private. Ask Pranit to add
  the optional dependency and launch/setup entry point; do not change shared manifests yourself.
- Search by project and conditions, inspect full evidence/history/relationships, explicit correction
  with expected version and source, and confirmed permanent deletion.
- Clear empty/loading/unavailable/unauthorized/stale-version states. On a 409 correction conflict,
  reload history and ask the user to review; do not silently retry against a newer version.
- A browse/status screen against Pranit's planned paginated API, using fake responses until the
  endpoint lands. Do not treat an empty query or search's maximum 20 results as a listing API.
- Accessible labels and ordinary language. Show uncertainty and the source of a memory, not
  implementation details a user does not need. Escape rendered content; never render arbitrary HTML.

Acceptance: another project cannot be inspected/edited through the selected view; evidence and
both versions are readable; a stale correction cannot overwrite the newer version; deletion
requires confirmation then refreshes the page. No token/private memory in global caches or logs.
Restarting the viewer does not erase service data, because HTTP service storage owns it.

Do the client and view-model tests immediately with fake responses. Once the UI dependency lands,
test real widgets/screens. Once the service is ready, rerun the flow against the real API.

## H4 — evaluation, product polish, and final evidence

Deliver:

- Synthetic or consented redacted labelled scenarios: paraphrases, exact identifiers, cross-project
  traps, changing decisions, historical queries, conditional conflicts, and forgotten memories.
- An evaluation runner comparing keyword baseline with semantic-only and full hybrid retrieval,
  plus end-to-end cases. Import Om's published formation results rather than editing his files.
- A fixed holdout set separate from tuning examples; record dataset/model/config/commit versions.
- Precision/recall at the returned-card limit, unsupported/stale-result rate, update/conflict
  correctness, latency distribution, provider calls/cost where available, and limitations.
- A clear report and demo showing why each returned card is appropriate. Improve the UI from a
  teammate's clean-install walkthrough, and record actual findings instead of claiming perfection.

Acceptance: the runner reproduces results on the recorded setup; safety cases have zero scope
leaks/deleted-content returns; quality/latency targets agreed after the baseline are met on
holdout cases. Empty output must not artificially count as perfect retrieval.
Real database/embedder/API tests and actual user walkthrough are recorded separately from fakes.

## Tests and PR sequence

Suggested PRs: H1 retrieval policy; H2 embedder/verification/graph; H3 viewer client then viewer UI;
H4 benchmark/report and polish. UI/evaluation work can progress while real vector wiring is pending.

After creating the test directories:

```text
uv run pytest tests/retrieval tests/inspection
uv run ruff check .
uv run ruff format --check .
```

Run the [required repository checks](../../AGENTS.md) before PR review; use a dedicated `_test`
database, not the developer's real memory store. Test behavior with adversarial input, not only
the happy fixture. Keep actual quality benchmarks separate from deterministic unit tests.

## What you hand to Pranit and Om

- Importable agreed entry points, fake repository/client, examples, and module test evidence.
- Shared API/vector/dependency requests with exact field names and expected failures.
- Real model metadata, evaluation runner/report, viewer instructions, and incomplete host checks.
- Formation-related failures go to Om as labelled examples; persistence/scope/queue failures go
  to Pranit. Fix only your owned module rather than modifying their code in your branch.

If shared types are pending, use dictionaries at the boundary. If pgvector is pending, continue
ranking, verification, benchmark cases, and viewer work. If the UI library is pending, complete
HTTP client/view-model tests and screen design. Actual full-stack gates remain pending until wired.

## Prompt for your coding agent

```text
Work on Harshal's next unfinished phase in docs/team-plan/harshal.md, within his assigned files.
Read AGENTS.md, README.md, docs/architecture.md, and docs/team-plan/contracts-v1.md first.
Create a focused feature branch from develop; all PRs target develop; never modify main.
Do not edit shared API/models/migrations/MCP/Compose/CI/pyproject.toml/uv.lock/root tests.
Implement agreed retrieval/embedder/viewer boundaries with injected repositories and HTTP clients.
Use fixtures and fake providers to proceed independently; clearly label pending real integration.
Preserve scope/time/conditions, source references, uncertainty, caller limits, and deletion checks.
The viewer must use the API and expected versions; never access SQL or cache private content globally.
Record shared requests in your module docs. Measure real retrieval quality against a fixed baseline.
Run meaningful module tests and full required checks; report fake, real-component, and product results separately.
Ask before changing common contracts or adding paid/private-data provider behavior.
```
