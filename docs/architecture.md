# Foundation architecture

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
  current version number, and create-request fingerprint.
- `memory_versions`: immutable content/evidence per revision, source agent/session/interaction,
  effective start/end, recording time, and current/historical status. Supersession closes the prior
  effective interval and changes its status; its content/evidence stay intact.
- `memory_edges`: version-to-version relationships. Explicit updates create `supersedes` edges.
  Other relation types are reserved for later policy implementation and are not publicly writable yet.

Scope/type/time/source constraints are also enforced in PostgreSQL. Foreign keys cascade forgetting
through versions and attached edges. The API never exposes a developer-ID override.

Updates lock the owning memory row and compare `expected_version`; competing clients cannot both
win. Unique `(developer_id, request_id)` constraints make concurrent create retries safe.

## Retrieval baseline

Apply configured owner, requested scope, conditions, and effective-time filters before selecting
results. Combine PostgreSQL English full-text matching with escaped case-insensitive literal matching
for identifiers. Order project matches first, then lexical relevance and deterministic tie-breaks.
Return at most the requested bounded set. Semantic retrieval and graph expansion are subsequent
milestones; no vector field or embedding model has been added prematurely.

## Deployment assumptions

V1 is single-developer and local-first. A shared bearer token authorizes the entire configured
developer's memory. Project scope is an explicit operation boundary, not a permission list per client.
Listen on localhost; the Compose database/API ports are loopback-only. Server deployments require
separate authentication, transport, authorization, and operational design.

Credentials are screened before persistence. Source evidence is retained for inspection but is not
automatically verified. Keep token/database URLs out of logs and commits. Logical deletion cannot
erase preexisting external copies, backups, or database recovery records.

## Design decisions still open

Admission weights, model choice, confidence calibration, automatic conflict policy, delayed/future
events, interaction evidence retention, capture-hook availability, vector indexes, and worker retry
contracts require experiments and later implementation. Codex and Claude Code are the initial
adapter targets; the engine remains agent-independent.
