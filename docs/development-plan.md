# V1 development backlog

The presentation notice requests a working prototype, tests, and results for 12–14 October 2026.
Track achieved behavior honestly; completion of this foundation does not mean 100% of V1.
For implementation, use the [three-member plan](team-plan/README.md) and its common contracts,
exclusive file ownership, individual phases, and release gates. The rows below track product
capabilities; they are not a sequential schedule that makes teammates wait for one another.

| Milestone | Status | Acceptance criteria |
| --- | --- | --- |
| Explicit memory foundation | Implemented | Persist across clients; isolate projects; inspect evidence/history; safe updates; forget |
| Agent interface | Protocol implemented; Pranit/Om report live Codex-to-Codex pass; Claude Code test pending | Six shared MCP tools; current/legacy stdio tested; actual supported hosts verified |
| Linux/Windows setup | Setup and native CI implemented; full-stack Windows host checks still required | Shared setup preserves credentials; native agent paths; full suite on Linux and Windows CI |
| Hybrid retrieval | Pending | Local embeddings + pgvector, lexical results, scope/time filtering, rank fusion, compact cards |
| Capture + extraction | Pending | Supported capture adapter feeds a durable buffer; configurable LLM returns validated candidates |
| Admission + conflicts | Pending | Reject filler/guesses/duplicates; resolve supported changes; preserve conditional facts; defer uncertainty |
| Background lifecycle | Pending | Celery/Redis process and retry events safely; selective consolidation preserves evidence |
| Evaluation + inspection | Pending | Streamlit viewer, labelled scenarios, measured retrieval/state accuracy, latency/cost, recorded demo |

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
