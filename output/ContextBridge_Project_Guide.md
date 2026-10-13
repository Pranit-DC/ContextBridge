# ContextBridge: a short project guide

**About 5-6 minutes.** Reviewed against `develop` snapshot `3b18501` on 13 October 2026. Technical explanations come first, then plain-language meanings.

## 1. What problem does it solve?

**Technical:** ContextBridge is a persistent, agent-independent memory service. Supported agents share developer/project context across sessions through HTTP or MCP (Model Context Protocol).

**Simple:** It is a shared notebook for AI coding assistants. One saves a decision; another reads it later without you repeating it. Restarting the assistant does not erase it.

V1 targets one developer on a local machine. It does not train models or archive the codebase; team accounts and automatic cross-device synchronization are outside its scope.

## 2. What is a memory?

**Technical:** An atomic memory holds one claim, type, scope, conditions, version, effective dates, source, and evidence. PostgreSQL separates identity, version content, and relationships.

**Simple:** Each note says one useful thing, where/when it applies, and where it came from. Corrections preserve earlier versions.

| Technical term | Simple meaning / example |
| --- | --- |
| `FACT`, `DECISION` | A project detail; a chosen approach: “Uses Python”; “Use PostgreSQL.” |
| `PREFERENCE`, `STATE` | A personal default; a changing situation: “Prefer type hints”; “Migration pending.” |
| `EVENT`, `LESSON` | Something that happened; reusable learning: “Migration completed”; “Check IPv4 settings.” |
| Project / developer scope | Applies to one project / potentially across this developer's projects. Global results require opt-in. |
| Conditions | Extra requirements: a production-only note appears only when the query supplies matching conditions. |
| Provenance / evidence | Agent, session, interaction, and original user/tool text supporting the note. Recording a source does not prove truth. |
| `ACTIVE` / `SUPERSEDED`; `contested` | Current / replaced version; a separate label meaning competing claims remain unresolved. |

## 3. How the pieces connect

```text
Agent -> MCP adapter -> authenticated HTTP API -> shared engine -> PostgreSQL
Viewer -----------------------> HTTP API
Imported conversation --------> capture job -> configured formation -> engine
Optional workers -------------> extraction / consolidation / vector indexing
Search -----------------------> filtered retrieval -> compact memory cards
```

**Technical:** The MCP adapter translates tool calls into API requests. The API authenticates and validates; engines enforce policy and transactions. Replaceable providers interpret content; PostgreSQL stores it.

**Simple:** Assistants and the viewer use one front door. The engine checks rules before changing the notebook. Agents must call the tools to save or read context.

MCP tools: `memory_write`, `memory_search`, `memory_retrieve`, `memory_inspect`, `memory_update`, `memory_forget`, and `memory_status`.

## 4. How information becomes stored memory

**Explicit writes** save authorized user/tool-backed notes directly. **Imported conversations** follow this pipeline, requiring configured providers and an engine caller or workers:

| Technical step | Simple explanation |
| --- | --- |
| Capture and normalization | Validate and queue a manually imported conversation for its project. Acceptance means received, not remembered. Raw text expires. |
| Extraction | An LLM (AI language model) proposes small, self-contained claims with source excerpts. Assistant suggestions alone cannot support durable claims. |
| Evidence and admission | Check support, usefulness, confidence, and duplicates. `ADMIT`: consider saving; `REJECT`: discard; `DEFER`: wait for evidence. Confidence is an estimate. |
| Relationship resolution | Compare existing notes: create, update, link conflict, keep unchanged, or defer. Semantic interpretation needs configuration; newer does not automatically mean correct. |
| Transactional commit | Recheck scope, evidence, cancellation, and version; save everything together or undo it all. Saved interpretations keep retries consistent. |
| Indexing and consolidation | Workers create searchable vectors and source-linked summaries. Summaries need configured proposals and validation. |

**Simple flow:** receive conversation -> find useful statements -> check them -> compare existing notes -> safely save -> prepare for future searches.

## 5. How searching works

**Technical:** `memory_search` and `/v1/memories/search` use keyword/full-text and identifier matching. Configured `memory_retrieve` and `/v1/retrieval/search` combine lexical, symbolic, and semantic channels through reciprocal rank fusion. Semantic search uses embeddings and pgvector.

**Simple:** Ordinary search matches words and names; richer search adds similar meaning. Embeddings represent text as number lists; similar lists suggest related meaning. Rank fusion combines several search lists.

Owner, project, conditions, and effective-time filters apply before limits. Rechecks exclude ineligible versions. Results are compact cards with content, version, source, and uncertainty labels: three by default, at most five through MCP. Inspect for full evidence.

Optional graph expansion follows related notes; selective verification checks risky results. Missing providers/stale vectors produce warnings or fallback. Specify environment/date filters explicitly. Viewer search remains keyword based.

## 6. Corrections, failures, and forgetting

| Technical mechanism | Simple meaning |
| --- | --- |
| `expected_version` + locks | Correct the version you read. Competing corrections cannot both win; stale updates conflict. |
| Versioning + `supersedes` edge | Link the correction to its old version. Historical queries retrieve what applied earlier. |
| Idempotent request/event IDs | Retrying the identical request avoids duplicate writes. Reusing an ID with different content conflicts. Never replay an old create after forgetting. |
| Durable outbox, leases, bounded retries | PostgreSQL remembers work; Redis carries IDs. Workers recover and recheck permission to save. Cancelled work cannot recreate deleted content. |
| Forget and retention cleanup | Remove stored versions, evidence, vectors, related derived content, and cancel associated jobs. External copies and database backups have separate retention. |

**Example:** Agent A saves “DemoApp API port is 8000.” B corrects it to “8080” with evidence and expected version 1. The engine creates version 2. C retrieves 8080; history still shows 8000. Forgetting removes both.

The bearer token is the service access key for one developer's store. Projects are data boundaries, not separate accounts. Secret screening is incomplete; stored text is untrusted. Errors omit rejected values/database details.

## 7. Where the implementation lives

Paths below are under `src/contextbridge/` unless stated otherwise.

| Code / technology | Responsibility, in simple words |
| --- | --- |
| [api.py](../src/contextbridge/api.py), [schemas.py](../src/contextbridge/schemas.py): FastAPI / Pydantic | HTTP front door, token checks, required data shapes. |
| [service.py](../src/contextbridge/service.py), [engine/](../src/contextbridge/engine/) | Explicit operations and safe capture/write/retrieval workflows. |
| [formation/](../src/contextbridge/formation/) | Om's extraction, admission, and consolidation proposals. |
| [retrieval/](../src/contextbridge/retrieval/), [persistence/](../src/contextbridge/persistence/) | Harshal's search policy; database queries, vectors, and cleanup. |
| [models.py](../src/contextbridge/models.py): SQLAlchemy; [migrations/](../migrations/): Alembic | Python database mapping; controlled changes to table structure. |
| [background/](../src/contextbridge/background/): Celery / Redis | Optional workers and reliable background delivery. |
| [runtime.py](../src/contextbridge/runtime.py), [contracts/](../src/contextbridge/contracts/) | Connect providers; agree on messages between modules. |
| [mcp_adapter/](../src/contextbridge/mcp_adapter/), [capture_adapters/](../src/contextbridge/capture_adapters/), [inspection/](../src/contextbridge/inspection/) | Agent tools, explicit import, and optional Streamlit viewer. |

Pranit owns the core, database, APIs, workers, integration, and shared files. Om owns formation; Harshal owns retrieval policy, viewer, and retrieval evaluation. Python 3.12 is the baseline; `uv.lock` fixes dependency versions.

## 8. What works, and what still needs validation?

**Available:** explicit memory operations, scope/condition/time filtering, evidence/history, durable import, write engine, PostgreSQL retrieval infrastructure, optional workers, MCP tools, and viewer.

**Opt-in:** Cloudflare Qwen3 supports real semantic indexing/retrieval. Groq `openai/gpt-oss-120b` formation adapters exist; shared production wiring needs a reviewed factory. Hosted providers receive configured inputs, even though storage is local.

**Remaining:** automatic host capture, formation/consolidation quality approval, broader retrieval evaluation, richer viewer cards, Claude Code/Windows Docker Desktop checks, and release review. V1 is incomplete. Recorded-provider tests and one small live embedding demonstration do not establish general AI accuracy. The retrieval target is under 500 ms for 95% of requests, not a measured guarantee.

## 9. Run it and judge it

From the repository root, with Git, uv, and Docker Compose installed:

```text
uv sync --frozen --all-extras --python 3.12
uv run python scripts/setup_local.py --project-id contextbridge
docker compose up --build -d
uv run python scripts/demo.py
```

Setup creates private credentials and agent snippets. Docker starts the database, migrations, and API. Open `http://127.0.0.1:8000/docs` and authorize with the API token. The demo uses clients, not live agents. See [agent registration](../Docs/agent-integration.md) and [provider/worker setup](../Docs/integrated-setup.md).

**Technical:** Evaluate extraction, admission, updates, retrieval, recovery, and deletion separately. Run Ruff lint/format; migrations, `alembic check`, and full tests require a dedicated PostgreSQL database ending in `_test`.

**Simple:** Check that information is correctly saved, updated, found, and removed, including after crashes. Passing code tests does not prove AI claims are correct.

For deeper reading only when needed: [README](../README.md), [architecture](../Docs/architecture.md), [requirements](../Docs/ContextBridge_SRS_v0.1.pdf), [methodology](../Guide/ContextBridge_Memory_Methodology_Explained_v1.md), and [team plan](../Docs/team-plan/README.md). Research papers explain design choices; the code and recorded checks establish what works.
