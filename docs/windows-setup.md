# Windows setup (PowerShell)

## 1. Install the prerequisites once

- Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), enable
  its WSL 2 backend, and use Linux containers. Follow Docker's Windows version, WSL, memory, and
  virtualization requirements. Complete any requested restart and launch Docker Desktop.
- You do not need to install PostgreSQL or Python separately for this route. `uv` installs Python
  3.12; Compose runs PostgreSQL 18, migrations, and the API in Linux containers.

Open a fresh PowerShell window after installation and check `git --version`, `uv --version`, and
`docker compose version`. Run `docker info` to confirm the Docker engine is running.

## 2. Prepare and start ContextBridge

Clone the repository, switch to the team's agreed branch, and open PowerShell in its folder.
Run these same commands on Windows or Linux:

```text
uv sync --frozen --python 3.12
uv run python scripts/setup_local.py --project-id contextbridge
docker compose up --build -d
docker compose ps -a
uv run python scripts/demo.py
uv run python scripts/mcp_demo.py --env-file .env.mcp
```

Successful startup shows `db` healthy, `migrate` exited with code 0, and `api` running. The demos
exercise memory operations and clean up their demo memory. They do not launch live models.
Open `http://127.0.0.1:8000/docs` to try the API manually; the **Authorize** button takes the token
from your private `.env`. It is a ContextBridge access token, not an LLM API key.

Setup generates credentials only for missing files. Rerunning it preserves existing `.env` and
`.env.mcp`, including custom ports and tokens, and regenerates native agent configuration snippets
under `.contextbridge/`. Those snippets contain paths, not credentials; Git ignores them.
Windows relies on your folder's existing access permissions; Linux creates credential files with
owner-only permissions. Keep the checkout in your private user folder.

## 3. Connect whichever coding agent you have

Use an installed agent with its normal working login. You can test Codex on your computer and
Claude Code on a friend's computer; neither computer needs both subscriptions. A local Compose
stack on each computer has separate data. To share memory across computers, both adapters must
reach the same service through a separately configured secure connection/tunnel; the current
adapter accepts only loopback URLs. Cross-platform support does not synchronize databases.

These commands are for agents running **natively on Windows**, from this checkout. They use
quoted absolute paths and work when the checkout's name includes spaces. First check readiness:

```powershell
$repo = (Get-Location).Path
& "$repo\.venv\Scripts\python.exe" -m contextbridge.mcp_adapter.cli --env-file "$repo\.env.mcp" --project-id contextbridge --agent-id codex --check
```

For Codex CLI, register the server and list it:

```powershell
codex mcp add contextbridge -- "$repo\.venv\Scripts\python.exe" -m contextbridge.mcp_adapter.cli --env-file "$repo\.env.mcp" --project-id contextbridge --agent-id codex
codex mcp list
```

For Codex desktop without the CLI, merge the section from `.contextbridge/codex-mcp.toml` into
your Codex MCP configuration (see the [official guide](https://learn.chatgpt.com/docs/extend/mcp)).
Keep other settings intact. Reopen the session after registering the server.

For Claude Code, run this instead and use `/mcp` in a new session to check the connection:

```powershell
claude mcp add --transport stdio --scope local contextbridge -- "$repo\.venv\Scripts\python.exe" -m contextbridge.mcp_adapter.cli --env-file "$repo\.env.mcp" --project-id contextbridge --agent-id claude-code
claude mcp list
```

Use your chosen project ID consistently in setup and registration. If the agent runs inside WSL,
install the checkout and `uv` environment inside WSL and follow the Linux instructions instead;
a Windows virtual environment cannot be reused as a Linux environment. Docker's WSL backend alone
does not require installing your agent inside WSL.

## 4. Checks and troubleshooting

- Docker connection error: start Docker Desktop and wait until its engine is ready.
- Port already in use: change `CONTEXTBRIDGE_DB_PORT` and the matching host port in
  `CONTEXTBRIDGE_DATABASE_URL` in `.env`; rerun `docker compose up -d`. The default is 5433.
- Migration failure: run `docker compose logs --no-color --tail=100 migrate`. Keep credentials
  private when sharing logs. Do not delete the database volume to fix an unexplained failure.
- Agent authentication error: ensure `.env.mcp` and the running API use the same token.
- Missing Python path: rerun `uv sync --frozen --python 3.12` and setup after moving the checkout.

Run lint and tests that do not need a database:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/test_validation.py tests/test_setup_local.py
```

For the full suite, first create a separate PostgreSQL database whose name ends in `_test`.
Then set **both** variables in this PowerShell session to that test database, never to the
development database (tests truncate tables):

```powershell
$env:CONTEXTBRIDGE_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5433/contextbridge_test'
$env:CONTEXTBRIDGE_TEST_DATABASE_URL = $env:CONTEXTBRIDGE_DATABASE_URL
uv run alembic upgrade head
uv run alembic check
uv run pytest --cov=contextbridge --cov-report=term-missing
Remove-Item Env:CONTEXTBRIDGE_DATABASE_URL
Remove-Item Env:CONTEXTBRIDGE_TEST_DATABASE_URL
```

CI runs the full PostgreSQL/migration/MCP suite on Linux and native Windows. Native Windows CI
uses PostgreSQL 17 preinstalled on the runner; Compose and Linux CI use PostgreSQL 18. Docker
Desktop startup and live agent conversations still need a manual check on your Windows computer.
Stop containers with `docker compose down`; adding `--volumes` permanently deletes stored data.
