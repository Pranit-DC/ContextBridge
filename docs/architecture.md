# ContextBridge V1 architecture

## Boundaries

FastAPI handles HTTP/authentication and request validation. `MemoryService` handles explicit memory
operations. SQLAlchemy and Alembic own persistence and schema evolution. The MCP adapter calls the
shared HTTP API; future capture adapters use the same operations. Inference providers are replaceable.
No model SDK is required to run the service. Server credentials and configured owner determine access.

The stdio MCP adapter is a separate local process per host. It has an explicit project binding and
API token, and no database connection. ID operations inspect and reject memories outside that project
before sending mutations; developer-global IDs are intentionally shared. Argument validation and
HTTP errors omit rejected inputs. Compact search cards contain source references; inspection provides
full evidence. Tool descriptions direct hosts to treat memory as untrusted data. See
[agent integration](agent-integration.md) for tool contracts, configuration, and retry behavior.

## Data model

- `memories`: stable identity, configured developer ID, project/developer scope, type, conditions,
  current version number, create-request fingerprint, and optional claim comparison label.
  A nullable retirement marker stops current use while preserving previous versions.
- `memory_versions`: immutable content/evidence per revision, source agent/session/interaction,
  effective start/end, recording time, and current/historical status. Supersession closes the prior
  effective interval and changes its status; its content/evidence stay intact.
  Nullable confidence and clear/contested decision state are separate from version lifecycle status.
- `memory_edges`: version-to-version relationships. Explicit updates create `supersedes` edges.
  The P2 engine also stages `contradicts` and scoped live `derived_from` relationships; these are
  not directly writable through HTTP. P4 validates injected consolidation proposals and commits derivation edges atomically.
- `embedding_models`/`memory_embeddings`: owner/model dimension registry and version-linked
  float32 arrays, content fingerprints, and index times; pgvector computes exact distance.
- `reindex_jobs`/`reindex_targets`: durable bounded ID/context-hash selections, safe status,
  and at-most-one committed batch. They contain no copied source text.

Scope/type/time/source constraints are also enforced in PostgreSQL. Foreign keys cascade forgetting
through versions and attached edges. The API never exposes a developer-ID override.

Updates lock the owning memory row and compare `expected_version`; competing clients cannot both
win. Unique `(developer_id, request_id)` constraints make concurrent create retries safe.

## Durable capture boundary (P1)

`contracts/` defines the version-1 module messages independently of existing explicit API shapes.
`engine/ingestion.py` commits a `capture_events` row and its unique `capture_jobs` row together.
The service supplies owner identity and requires an explicit capture-project binding; optional
developer-global ingestion requires opt-in. A transaction-scoped owner lock serializes replay
and raw-buffer capacity decisions across processes. Accepted jobs remain queued until a caller
invokes the P2 processing library; the optional P4 scheduler publishes their durable outbox IDs.

The event stores a normalized payload, replay fingerprint, receipt time, and fixed expiry time.
Expiry clears payload and fingerprint transactionally, cancels pending work, and retains an
identity marker that rejects stale redelivery. The maintenance command handles idle services;
ingestion and job-status access also sweep the configured scope. See [ingestion](ingestion.md)
for binding, retention, API errors, and operational limits. `ModuleGateway` accepts injected
interfaces with no fake production defaults; fixture-backed tests do not prove real integration.

## Candidate execution and browse (P2)

`engine/write.py` persists extraction exactly once into ordered `capture_candidates`, then saves
each admission decision and write plan before execution. Candidate replay IDs survive expiry as
content-free metadata. Provider calls release transaction locks; commit reacquires the owner lock
and checks evidence, live scope/conditions, expiry, target identity, and expected version. The
default resolution policy accepts exact duplicates/new claims and defers uncertain relationships;
semantic proposals require an injected interpreter. The P5 runtime assembles merged modules;
real provider quality remains pending.

Updates, engine writes, derivation edges, and forgetting share one transaction-scoped owner lock.
Forgetting clears related raw/candidate/plan content and cancels jobs in the deletion transaction.
It also removes a bounded transitive derivation closure. P3 adds vector/reindex fences;
P4 adds outbox cancellation, consolidation provenance, execution deadlines, and worker recovery.
`persistence/` supplies filtered version queries and capture cleanup. Browse filters owner,
scope/project, conditions, and effective time before limits, with a signed cursor fixing the
query time across pages. See [write engine](write-engine.md) for invocation and limitations.

## Retrieval baseline

Apply configured owner, requested scope, conditions, and effective-time filters before selecting
results. Combine PostgreSQL English full-text matching with escaped case-insensitive literal matching
for identifiers. Order project matches first, then lexical relevance and deterministic tie-breaks.
Return at most the requested bounded set. The legacy API/MCP keeps this keyword baseline.

P3 `PostgresRepository` separately implements the agreed lexical, symbolic, and exact pgvector
channels plus bounded authorized graph/inspection/liveness reads. Scope/time/conditions and
model/dimension/fingerprint eligibility apply before channel limits. Missing/stale embeddings
report degradation. Native core-only PostgreSQL stores the same schema and keeps keyword APIs
usable; pgvector is required for semantic distance. The new V1 HTTP endpoint calls an injected
retriever, then compares cards to fresh stored fields under the owner lock. Default real provider
wiring is configured through [integrated setup](integrated-setup.md); model quality remains pending.
See [retrieval persistence](retrieval-persistence.md).

## Deployment assumptions

V1 is single-developer and local-first. A shared bearer token authorizes the entire configured
developer's memory. Project scope is an explicit operation boundary, not a permission list per client.
Listen on localhost; the Compose database/API ports are loopback-only. Server deployments require
separate authentication, transport, authorization, and operational design.

Credentials are screened before persistence. Source evidence is retained for inspection but is not
automatically verified. Keep token/database URLs out of logs and commits. Logical deletion cannot
erase preexisting external copies, backups, or database recovery records.

## Design decisions still open

Groq and hosted Cloudflare Qwen embeddings are selected for this V1. No local model is required.
Admission calibration, model accuracy, semantic duplicate reliability, consolidation usefulness and
larger-scale retrieval performance still require evaluation. Future-effective writes and automatic
host capture remain outside this agreed V1. Bounded retries, retention and safe conflict proposals
are implemented; their limits are documented rather than left as implicit release promises.

## Optional background stack (P4)

`background/` owns the ID-only PostgreSQL outbox, leases, bounded attempts, publication, recovery,
and retention. Celery/Redis run in Linux containers on either OS. Domain engines check fresh
lease tokens/deadlines under the owner lock before commits. Injected calls release locks; expired
or cancelled work cannot resurrect deleted content. Source-linked consolidation selections and
saved proposals are erased when their source or summary is forgotten. Before interpretation,
forget clears the same scope's raw capture buffers conservatively. No server content cache is
added. See [workers](workers.md) for setup, status, retention, and exact limits.

## Configurable assembly and adapters (P5)

`runtime.py` wraps approved local backends in Om's Extractor/AdmissionPolicy and Harshal's
GuardedEmbeddingProvider/Retriever/EvidenceVerifier. The same integration factory serves API and
workers, with an authorized EventReader and shared embedding metadata. The scheduler recovers
current-version indexing from durable versions in bounded batches; models are called by workers,
never during discovery. New/corrected versions can temporarily retrieve lexically while indexing
is pending, with explicit degradation. No source content is added to the outbox.

`capture_adapters/` validates explicit bounded transcript imports with Om's normalizer and submits
to the ingestion API. It owns no persistence, capture hooks or automatic retries. The additional
MCP `memory_retrieve` exposes V1 cards without changing the original lexical/write interfaces.
The built-in runtime assembles hosted formation/checking/duplicate/consolidation providers and
Cloudflare embeddings without a custom factory. Fresh providers serve each execution/request;
account-wide numeric PostgreSQL quotas serialize Groq calls across API and workers. A cancellation
check follows quota waiting before a hosted formation request. Providers propose; engines authorize
and commit. See [V1 integration](v1-integration.md).

Automatic consolidation is opt-in: one batch every 15 minutes, at most 20 compatible current clear
memories. Derived, retired and disputed records are excluded; unchanged source sets are not repeated.
Retirement closes validity intervals and affected summaries and cancels work. Restoration creates a
new version from user-supported history; forgetting removes the bounded derivation closure and
content-bearing artifacts. The existing viewer calls these additive management APIs and exposes
original summary evidence. The original seven MCP interfaces retain their shapes, with retire and
restore added. See [lifecycle](memory-lifecycle.md), [viewer](inspection/README.md) and
[observed verification](v1-completion.md). General model quality, actual Claude and Windows Docker
Desktop checks remain separate from implemented wiring and synthetic regressions.
