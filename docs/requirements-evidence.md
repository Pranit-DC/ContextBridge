# Requirements-to-evidence map

Source: `Docs/ContextBridge_SRS_v0.1.pdf`, provisional version 0.1, plus the
user-accepted end-to-end definition in [remaining work](remaining-work.md).
This maps implementation evidence; it is not independent release acceptance.
Tests listed here are executable files, not a claim that every research-quality
criterion has an agreed quantitative target or has been independently approved.

| SRS requirement | Implementation/test evidence | Acceptance limit |
| --- | --- | --- |
| FR-01 persistent storage | `service.py`; `tests/test_memory_api.py`, `tests/test_mcp_stdio.py` | Actual promised-host review remains separate |
| FR-02 cross-agent interface | `mcp_adapter/`; `tests/test_mcp_stdio.py` | Actual Claude host is pending |
| FR-03 scopes / FR-04 isolation | `schemas.py`, `persistence/repository.py`; `tests/integration/test_repository.py` | Single configured developer; project labels are not multi-user permissions |
| FR-05 selective admission | `formation/admission.py`; `tests/integration/test_phase4_admission.py`; live duplicate example | Representative independent admission targets/review pending |
| FR-06 LLM assistance | `runtime.py`; `tests/test_runtime.py`; fresh live lifecycle report | Approved built-in providers and replaceable injected backend; broad model quality pending |
| FR-07 async processing | `background/`, `engine/consolidation.py`; `tests/background/`, compaction foreground regression | Actual concurrent hosted-load latency is not established |
| FR-08 conflicts | `engine/resolution.py`, `engine/write.py`; `tests/integration/test_conflict_comparison.py` | Automatic semantic conflict/correction quality remains open |
| FR-09 supersession | `service.py`, `engine/write.py`; `tests/integration/test_write_engine.py`, live correction/history | Representative automatic transitions require review |
| FR-10 temporal validity | version intervals, `engine/relative_time.py`; `tests/integration/test_relative_time_boundary.py` | Explicit aware timestamps/UTC; richer ranges/source-zone contract unresolved |
| FR-11 provenance | version sources/edges; `tests/test_memory_api.py`, `tests/background/test_consolidation.py` | Cross-event evidence extension unresolved |
| FR-12 selective retrieval | `engine/retrieval.py`; `tests/integration/test_retrieval_api.py` | Representative relevance acceptance pending |
| FR-13 adaptive depth | `engine/context.py`, bounded graph retrieval; `tests/integration/test_graph_depth.py`, `test_memory_context.py` | Explicit bounded expansion; reviewed usefulness pending |
| FR-14 hybrid retrieval | real SQL/pgvector, fusion; `tests/integration/test_repository.py`, `test_pipeline_benchmark.py` | Authored-vector comparisons and live smoke examples are not held-out model accuracy |
| FR-15 durable outcomes | capture/admission boundary; `tests/formation/test_admission_examples.py` | Representative useful-outcome selection still needs review |
| FR-16 code references | `persistence/related.py`; `tests/integration/test_related_links.py` | Shared evidenced code-reference rule, not general semantic graph inference |
| FR-17 secret protection | `security.py`; `tests/test_validation.py`, capture/API rejection tests | Recognized common-secret screening is not exhaustive sensitive-data detection |
| FR-18 management | `engine/lifecycle.py`, `engine/compaction.py`, API/UI; `tests/integration/test_lifecycle.py`, `test_compaction.py`, `test_local_workspace.py` | Compaction is exact-claim retirement; independent UX review pending |
| FR-19 pluggable LLM | `runtime.py`, injected factory; `tests/test_runtime.py` | Future local-model deployment is not required or claimed tested |
| FR-20 explicit memory | API/MCP create; `tests/test_memory_api.py`, `test_mcp_stdio.py` | Writes require user/tool evidence |
| NFR-01 latency | raw offline pipeline latency samples | SRS approximately <500 ms p95 target requires accepted representative transport/load measurements |
| NFR-02 responsiveness | provider work outside transaction; blocked-provider foreground test | This is a deadlock regression, not a hosted-load SLO |
| NFR-03 privacy / NFR-04 isolation | scope/secret/lifecycle suites; private settings tests | Independent review and real supported-host walkthroughs remain |
| NFR-05 model independence / NFR-06 extensibility | shared service, module protocols and adapters | Multi-tenant/server/local-model expansion is future scope |
| NFR-07 auditability | preserved versions, evidence, derivations; lifecycle tests | Pending independent provenance review |
| NFR-08 efficiency | group/replay/index discovery; `tests/integration/test_session_groups.py`, `tests/background/test_consolidation.py` | Broader provider cost/efficiency measurement pending |
| NFR-09 maintainability | API/policy/persistence/module separation; required lint/format and full tests | Team review remains required |
| NFR-10 reliability | `tests/test_availability.py`, background recovery and capture cleanup suites | Final-head CI/OS acceptance remains separate |

## Accepted completion criteria beyond a unit test

The accepted full lifecycle is exercised by the synthetic live report and the UI
integration suite, and hard scope/evidence/version/failure boundaries have direct
regressions. Final completion additionally requires reviewed quality targets and
results, all promised supported agents/environments, independent installation and
usability/accessibility review, complete delivery evidence and stakeholder approval.
See [current status](completion-status.md) rather than inferring approval from this map.
