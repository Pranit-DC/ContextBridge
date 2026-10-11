# Retrieval (H1 policy, H2 embeddings, verification, expansion)

`contextbridge.retrieval.Retriever.search(query, repository, embedder, verifier)` turns a
`RetrievalQuery` into a `RetrievalResult` of compact cards, using the shapes in
[contracts V1](../team-plan/contracts-v1.md). It owns no store: all reads go through the injected
repository, and it makes no database or network call itself.

## Status

| Part | State |
| --- | --- |
| Query validation, fusion, applicability checks, cards, degradation (H1) | Implemented; tested with fakes |
| Embedding guard (batching, deadline, validation) and a deterministic fake | Implemented; tested with fakes |
| **A real embedding model** | **Pending**: needs a team decision and a dependency request |
| Evidence verifier and selective verification | Implemented; needs a real judge to ever say `supported` |
| Bounded graph expansion | Implemented; off by default; tested with a fake graph |
| Real repository (PostgreSQL channels, pgvector, graph walk) | Pending; Pranit owns it, see [integration request](integration-request.md) |
| `POST /v1/retrieval/search` endpoint, MCP card adaptation | Pending; Pranit owns them |
| Measured quality against the keyword baseline | Pending (H4) |

Everything above that is "tested" was tested against fakes. Nothing here is semantic retrieval
until a real repository serves the `semantic` channel with a real embedder. The fake embedder
hashes words and captures no meaning.

## What a search does

1. **Validate** the query. Secrets, bad limits, naive timestamps, unknown fields, or the wrong
   `schema_version` raise `ModuleError("INVALID_INPUT")` with no echoed input. Only whitespace is
   normalized, so identifiers and paths survive. `as_of` defaults to the current time, fixed once
   for every stage. Scope, project, conditions, and limit are never changed or inferred.
2. **Embed** the query text once. Failure, malformed output, or a model/size other than the one
   named in `RetrievalConfig.embedding_model_id` / `embedding_dimensions` skips the semantic
   channel and adds `EMBEDDING_UNAVAILABLE`.
3. **Ask each channel** (`lexical`, `semantic`, `symbolic`) for at most `channel_limit` matches.
   The lexical channel failing raises a retryable `STORAGE_UNAVAILABLE`; the others degrade.
4. **Re-check every match** against the caller's project (or developer scope with
   `include_developer`), every stored condition, and the effective interval `[valid_from, valid_to)`
   at `as_of`. Malformed or mislabelled matches are dropped.
5. **Fuse** with reciprocal rank fusion: a version scores `sum(1 / (k + rank))` over the channels
   that returned it, at its best rank in each. Duplicates collapse by version ID. Order is project
   before developer memory, then score, then newer memory, then version ID, so ties are
   deterministic.
6. **Check liveness** of each candidate in order and stop at the caller's `limit`. A record that is
   not live is skipped and the next candidate takes its place. If liveness cannot be checked, the
   record is withheld (fail closed).
7. **Expand** (only if `expand_graph` is on) to fill spare slots with related memories; see below.
8. **Verify** selected cards (only if a verifier is supplied); see below.
9. **Return cards** with source references only; full evidence needs inspection.

Contested memories keep `decision_state: "contested"`. No card is invented to fill a slot: an empty
result returns `cards: []` and the warning `NO_RESULTS`.

## Embedding providers

`GuardedEmbeddingProvider(backend, model_id=..., dimensions=...)` wraps any object with
`embed_batch(texts) -> list[list[float]]`:

- Input is bounded (count, 8,000 characters each), and texts containing credentials are rejected
  before any backend call.
- Calls go out in fixed-size batches under one overall deadline. A call that exceeds it is
  abandoned, not killed: its worker thread can keep running until the backend returns.
- Output must be exactly one finite vector of the declared size per text, labelled with the
  declared model. Anything else is `INVALID_PROVIDER_OUTPUT`; backend failure or timeout is a
  retryable `EMBEDDING_UNAVAILABLE`. Provider error text is never surfaced.

`FakeEmbeddingProvider` gives deterministic word-hashing vectors for tests and demos only.

**Choosing a real model** is open. Decide with the team on: language coverage (code and English
text), RAM and CPU/GPU needs, download size, license, vector size (affects Pranit's index), and
measured retrieval quality on the H4 holdout set. No model or dependency has been added.

## Verification

`EvidenceVerifier(judge)` checks that an authorized inspection describes exactly the card's version
(id, content, status, validity, source, and evidence) and that the decision is not contested. It
returns `supported` only if an injected `EvidenceJudge` says the evidence supports the claim.
Word overlap, vector scores, and model confidence are never used. With no judge, a judge error,
a mismatch, contested state, or evidence containing a credential, the answer is `uncertain`.
Writing a real judge (for example an LLM or entailment model) is a provider decision that is still
open; until then every verified card is honestly `uncertain`.

The retriever verifies only cards that warrant it: contested decisions, records whose `confidence`
is below `verify_below_confidence` (0.7), and memory types in `verify_types` (empty by default),
at most `max_verifications` (3) per search. Verification labels a card and never removes it.

## Graph expansion

With `expand_graph=True`, spare card slots are filled with memories related to the direct matches,
for up to `max_hops` (1 to 3) hops. It never exceeds the caller's `limit`, never displaces a direct
match, and does nothing when the limit is already met or there is no direct match. Every related
record is re-checked for scope, conditions, time, and liveness, deduplicated against everything
already seen (which stops cycles), and a record that fails a check is not walked through.
Related cards cannot be marked in contracts V1, so `RELATED_MEMORIES_INCLUDED` is added to the
result's warnings. Off by default because related is not the same as relevant until H4 measures it.

## Warnings

`degraded` is true when any warning ends in `_UNAVAILABLE`.

| Warning | Meaning |
| --- | --- |
| `EMBEDDING_UNAVAILABLE` | Query embedding failed or came from an unexpected model; semantic search was not used |
| `SEMANTIC_UNAVAILABLE`, `SYMBOLIC_UNAVAILABLE` | That channel failed; results come from the others |
| `LIVENESS_UNAVAILABLE` | A candidate could not be confirmed live and was withheld |
| `VERIFICATION_UNAVAILABLE` | Inspection failed; the card is labelled `uncertain` |
| `EXPANSION_UNAVAILABLE` | The graph walk failed; direct results are returned |
| `INVALID_MATCHES_DROPPED` | The repository returned malformed or wrongly labelled records |
| `VERIFICATION_LIMIT_REACHED` | More cards warranted verification than `max_verifications` allows |
| `RELATED_MEMORIES_INCLUDED` | At least one card came from graph expansion, not a direct match |
| `NO_RESULTS` | Nothing applicable and live was found |

These codes are this module's own and extend the shared vocabulary for retrieval results only.

## Configuration

`RetrievalConfig` defaults: `rrf_k=60`, `channel_limit=50`, `verify_below_confidence=0.7`,
`max_verifications=3`, `expand_graph=False`, `max_hops=1`. None of these has been tuned; H4 should
evaluate them on a holdout set before anyone relies on them.

## Tests

```text
uv run pytest tests/retrieval
```

The fake repository deliberately returns unfiltered, out-of-scope, stale, and malformed records
to exercise the defensive checks. Passing these tests shows the policy is correct; it does not
show real SQL, vectors, graph walks, or model quality.
