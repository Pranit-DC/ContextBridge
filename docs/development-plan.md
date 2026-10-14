# V1 development backlog

The presentation notice requests a working prototype, tests, and results for 12–14 October 2026.
Track achieved behavior honestly; completion of this foundation does not mean 100% of V1.
For implementation, use the [three-member plan](team-plan/README.md) and its common contracts,
exclusive file ownership, individual phases, and release gates. The rows below track product
capabilities; they are not a sequential schedule that makes teammates wait for one another.

| Milestone | Status | Acceptance / evidence |
| --- | --- | --- |
| Explicit memory and lifecycle | Implemented | Source-backed writes, history, version fences, retire/restore and full forgetting |
| Agent interface | Nine tools implemented; actual Codex lifecycle passed; Claude pending by user choice | Legacy seven compatible; actual-host proof separate from protocol tests |
| Linux/Windows operation | Linux full stack passed; native CI green; Windows Docker Desktop pending | Dedicated test stores; same Compose lifecycle/restart probe for both OSes |
| Shared engine and ingestion | Merged P1–P5, connected to real adapters | Bound imports, saved interpretations, scopes, conditions, uncertainty and durable replay |
| Hosted indexing/retrieval | Implemented with Cloudflare Qwen; observed live indexing/paraphrase | Meaning/words/identifiers, historical vectors, bounded graph and warning-preserving cards |
| Formation and conflicts | Built-in Groq runtime and conservative interpreter implemented | Actual import worked; live duplicate failed and evidence checking returned HTTP 400; quality remains open |
| Consolidation/workers | Durable bounded scheduling, proposal/source checks and cancellation implemented | Full synthetic integration passes; live consolidation unattempted after provider stop |
| Viewer/setup/demo | V1 controls and repeatable checks implemented | Read [V1 guide](v1-guide.md), [viewer](inspection/README.md) and [honest check report](v1-completion.md) |

The approved V1 uses **online Groq and Cloudflare**. A subsequent Linux reliability extension adds
an opt-in Codex user-prompt hook and a one-command launcher; see [Linux V1](linux-v1.md). Broader
conversation/other-host capture, SaaS/multi-user work, Mem0-style visual polish and future-effective
writes remain outside this scope. Implementation completion
is distinct from general model-quality or release approval. See the report for failures and pending
checks rather than treating test-substitute passes as live model proof.

## Three-member ownership

1. [Pranit](team-plan/pranit.md): storage, APIs, shared contracts, conflict mutation, workers,
   capture/MCP adapters, integration, and operational reliability.
2. [Om](team-plan/om.md): extraction, evidence/usefulness admission, normalization,
   consolidation proposals, and formation quality evaluation.
3. [Harshal](team-plan/harshal.md): hybrid retrieval, validity/evidence ranking, inspection UI,
   retrieval/end-to-end evaluation, and demo evidence.

Use [contracts V1](team-plan/contracts-v1.md) and its sample data before parallel development.
Separate owned directories and fake providers/repositories permit independent implementation.
Pranit owns shared files and connects merged modules; complete product validation uses real
components. Every milestone includes tests for its actual failure modes. Model credentials are
needed only for a chosen hosted provider; fake/local development does not require subscriptions.

## First foundation review checklist

- Run full PostgreSQL integration tests and migration round trip.
- Review evidence handling, scope boundaries, conditional retrieval, and deletion.
- Linux Compose startup and both protocol demos verified; verify Docker Desktop and live agents on Windows.
- Enable required CI and branch protection in GitHub after the workflow lands.
- MCP protocol/shared-service tests pass; retain the reported Codex-to-Codex result and run pending
  Claude Code, same-device cross-agent, and full-stack Windows host checks.
- Next work runs in parallel: Pranit's ingestion/storage, Om's extraction/admission, and Harshal's
  retrieval/viewer contracts. Record real provider/dataset choices before quality evaluation.
