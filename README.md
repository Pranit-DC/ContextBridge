# ContextBridge

Persistent, agent-independent memory for developers and projects. A shared service keeps useful
facts, decisions, preferences, state, events, and lessons outside any model's private session.

## Current milestone

The first foundation supports explicit memory creation, scoped keyword/identifier search,
evidence/history inspection, version-checked updates, and permanent forgetting. It uses Python,
FastAPI, PostgreSQL, SQLAlchemy, and Alembic. All memory endpoints require a bearer token.

**This is a foundation, not the complete V1.** Automatic capture, LLM extraction/admission,
semantic search, automatic conflict interpretation, MCP adapters, workers, consolidation,
and the inspection UI are still pending. Updates here are explicit human/tool-supported corrections.
Search does not infer synonyms, intent, environment, or dates from natural language.

Read [architecture](docs/architecture.md) and [development plan](docs/development-plan.md).
The methodology is in `Guide/`, the SRS and architecture illustration in `Docs/`, and research in `Papers/`.

## Local development

Prerequisites: Git, [uv](https://docs.astral.sh/uv/), and PostgreSQL 18 (or Docker Compose).
Python 3.12 is the baseline for local tests, CI, and containers. `uv sync` installs it if needed.

```bash
uv sync --frozen
cp .env.example .env
```

Replace both placeholders in `.env`. Generate the API token and database password separately with
`uv run python -c 'import secrets; print(secrets.token_hex(32))'`.
Using hex avoids URL-escaping problems in the database connection string. Keep `.env` private.

**Docker Compose:**

```bash
docker compose up --build -d
```

The database is checked for readiness, migrations run once in a separate service, then the API starts.
API and database ports are published only on `127.0.0.1`. Data persists in a named volume.
Use `docker compose down` to stop; adding `--volumes` permanently removes database data.
If port 5432 is in use, change the host port and `.env` host database URL together.

**Existing PostgreSQL installation:** create a database and dedicated role, set
`CONTEXTBRIDGE_DATABASE_URL` in `.env` to that database, then run:

```bash
uv run alembic upgrade head
uv run uvicorn contextbridge.main:app --host 127.0.0.1 --port 8000
```

Migrations are explicit; application startup never creates or modifies tables automatically.
Open `http://127.0.0.1:8000/docs` for the interactive API reference. Use **Authorize** to enter the
API token. This is a single-developer local service: the token grants access to that developer's
projects. It is not per-project authorization or a multi-user login system.

## Try the complete flow

After starting the service:

```bash
uv run python scripts/demo.py
```

The script reads settings from `.env`, writes a PostgreSQL decision with Codex source metadata,
retrieves it using an independent HTTP client, applies a Claude Code-sourced SQLite decision,
checks the preserved history, and forgets the demo memory. It exercises the shared API;
it does **not** launch or connect real agents. It creates no lasting demo memory on success.

## API contract

See `/docs` or `/openapi.json` for complete request schemas. Send
`Authorization: Bearer <CONTEXTBRIDGE_API_TOKEN>` for all memory operations.

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/v1/memories` | Explicit write with `request_id`, content, type, scope, source, optional conditions/time |
| POST | `/v1/memories/search` | Query text plus explicit scope/project, conditions, optional `as_of`, and limit |
| GET | `/v1/memories/{id}` | Current memory, all versions/evidence, and relationships |
| PUT | `/v1/memories/{id}` | Correction with `expected_version`, content, evidence, optional effective time |
| DELETE | `/v1/memories/{id}` | Permanently remove memory, every version/evidence, and attached edges |
| GET | `/health/live` | Process liveness, without credentials |
| GET | `/health/ready` | Authenticated check that the database/schema can be queried |

Create uses a client-generated UUID `request_id`. Repeating the same request returns the same
memory; reusing the UUID with different content returns 409. After updates, replay returns the
original version alongside the latest `current_version`. Forget removes the request association
too, so clients must not retry old creates after forgetting.

Update must name the current version; stale or competing writes return 409. On a lost update
response, inspect before retrying. Every accepted update creates a version and `supersedes` edge
in one transaction. Updates do not change type, scope, or conditions; create a separate memory
for a different environment. Future-effective and backdated-out-of-order updates are not supported
yet. Dates must include a timezone; responses use UTC. Validity intervals are `[from, to)`.

Project retrieval excludes unrelated projects. Developer-global memories are included only when
`include_developer` is true, and project results rank first. Conditional memories are returned only
when **all** stored conditions match the request; unconditional memories remain applicable.
The default limit is 3, maximum 20. Historical searches evaluate effective time and may return
a version now marked `SUPERSEDED`.

Evidence/source metadata are client-supplied; schema checks and secret screening do not establish
truth. Only `user` or `tool` source kinds are accepted for this explicit-write milestone. Common
credential patterns are rejected in all persisted request fields; this is not an exhaustive detector.
Rejected values and SQL exceptions are not echoed. Memory text remains untrusted context for agents.
Deletion removes logical stored records; PostgreSQL backups/WAL and external client copies require
their own retention policy.

## Checks and tests

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/test_validation.py
```

For the full suite, create a **dedicated test database ending in `_test`** and point both variables
below to it. The tests truncate memory tables; never use a database containing valuable data.

```bash
export CONTEXTBRIDGE_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost/contextbridge_test'
export CONTEXTBRIDGE_TEST_DATABASE_URL="$CONTEXTBRIDGE_DATABASE_URL"
uv run alembic upgrade head
uv run alembic check
uv run pytest --cov=contextbridge --cov-report=term-missing
```

Without `CONTEXTBRIDGE_TEST_DATABASE_URL`, integration tests explicitly skip. CI always supplies
PostgreSQL and runs the full suite, migration drift check, and downgrade/upgrade on its disposable DB.

## Team workflow

Use a separate branch for each task and small pull requests targeting `main`. Agree on schema/API
changes before dependent work. A PR should explain the behavior, acceptance criteria, test evidence,
and remaining limitations. Enable branch protection and required CI checks in GitHub once the first
workflow is available. See `AGENTS.md` for contributor and coding-agent instructions.
