# V1 development backlog

The presentation notice requests a working prototype, tests, and results for 12–14 October 2026.
Track achieved behavior honestly; completion of this foundation does not mean 100% of V1.

| Milestone | Status | Acceptance criteria |
| --- | --- | --- |
| Explicit memory foundation | Implemented | Persist across clients; isolate projects; inspect evidence/history; safe updates; forget |
| Agent interface | Pending | Codex and Claude Code call the same search/write/inspect/forget tools via MCP |
| Hybrid retrieval | Pending | Local embeddings + pgvector, lexical results, scope/time filtering, rank fusion, compact cards |
| Capture + extraction | Pending | Supported capture adapter feeds a durable buffer; configurable LLM returns validated candidates |
| Admission + conflicts | Pending | Reject filler/guesses/duplicates; resolve supported changes; preserve conditional facts; defer uncertainty |
| Background lifecycle | Pending | Celery/Redis process and retry events safely; selective consolidation preserves evidence |
| Evaluation + inspection | Pending | Streamlit viewer, labelled scenarios, measured retrieval/state accuracy, latency/cost, recorded demo |

## Suggested ownership

1. Storage, APIs, migration contracts, and integration.
2. Extraction, evidence/admission, and conflict interpretation.
3. Hybrid retrieval, validity ranking, and evaluation data.
4. MCP/capture adapters, inspection UI, and demo.

Share schemas and operation contracts before parallel development. Separate branches and small PRs
allow modules to integrate regularly. Every milestone must include tests for its actual failure modes.
Model selection/API credentials are needed when starting extraction, not for the foundation.

## First foundation review checklist

- Run full PostgreSQL integration tests and migration round trip.
- Review evidence handling, scope boundaries, conditional retrieval, and deletion.
- Verify Compose on a machine with Docker (unavailable in the initial development host).
- Enable required CI and branch protection in GitHub after the workflow lands.
- Next branch: MCP tools using the shared service, with Codex/Claude Code installation instructions.
