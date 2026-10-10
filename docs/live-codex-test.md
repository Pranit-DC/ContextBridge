# Test ContextBridge with Pranit and Om using Codex

Yes, two Codex instances can use the same ContextBridge memory service. Each computer runs
its own MCP adapter, and both adapters connect to the service on Pranit's computer.

This guide assumes **Pranit uses Fedora/Linux** and **Om uses Windows PowerShell**, matching the
team's Windows setup. Both use Codex on their own computers, on different networks.
Send Om this page and the linked connection page. Follow the numbered steps together.

**The goal:** Pranit saves a decision, Om retrieves and changes it, a fresh Codex chat on
Pranit's computer sees the change and history, and Om verifies deletion.

This tests shared memory between two real Codex clients. It does not replace the later
Codex + Claude Code test: Claude Code's actual integration still needs its own check.

## Before starting

| Person | Needs | Runs the database? |
| --- | --- | --- |
| Pranit | Repo, Git, uv, running Docker, and Codex with a working login | Yes |
| Om | Repo, Git, uv, and Codex with a working login | No; Docker is not needed |
| Both | Internet, their own Tailscale accounts, and this guide | |

Use your own Codex accounts. You do not need to share a Codex account or buy a separate LLM
API key for this test. The **ContextBridge API token** is a password for the memory service;
it is separate from your Codex login. **MCP** lets Codex call ContextBridge's tools.

We will use these names throughout:

| Setting | Pranit | Om |
| --- | --- | --- |
| MCP server name | `contextbridge-codex-pair` | `contextbridge-codex-pair` |
| Project ID | `contextbridge-codex-test` | `contextbridge-codex-test` |
| Agent ID | `codex-pranit` | `codex-om` |
| API address | `http://127.0.0.1:8000` | `http://127.0.0.1:18000` through the tunnel |

Agent IDs are labels recorded in memory history, not separate login accounts or access rules.
The project ID must match; the agent IDs should differ so you can identify each person's changes.
`127.0.0.1` means "this computer." The tunnel carries Om's local requests to Pranit's service.

Commands go in a terminal; prompts go in a Codex chat. Wait for each command to finish.
If a step fails, use the troubleshooting section before continuing.

## Step 1 — Pranit: open the repo

Open a Linux terminal:

```bash
cd /home/pranitchiman/Projects/ContextBridge
git status --short
```

If Git lists unfinished changes, save/commit them before switching branches. Then run:

```bash
git switch develop
git pull --ff-only origin develop
uv --version
docker info
```

**Success:** you are on `develop`, uv prints a version, and Docker prints information.
These instructions use the implementation already on `develop`; the guide can be read from
the draft PR before it is merged.

## Step 2 — Pranit: start the service

In the same terminal:

```bash
uv sync --frozen --python 3.12
uv run python scripts/setup_local.py --project-id contextbridge-codex-test
docker compose up --build -d
docker compose ps -a
```

Setup creates missing credential files and keeps existing credentials. In the container list:

- `db` should be **healthy**.
- `migrate` should show **Exited (0)**; it finished preparing the database.
- `api` should be **Up**.

Check the adapter:

```bash
repo="$(pwd)"
uv run python -m contextbridge.mcp_adapter.cli --env-file "$repo/.env.mcp" --project-id contextbridge-codex-test --agent-id codex-pranit --check
```

**Success:** the output includes `"status": "ready"`, `"project_id": "contextbridge-codex-test"`,
and `"agent_id": "codex-pranit"`.
If authentication fails, make the `CONTEXTBRIDGE_API_TOKEN` values in `.env` and `.env.mcp`
match using your editor. Keep them private. Do not generate new credentials just to repeat a test.

## Step 3 — Both: connect the two computers

Follow [Connect a friend on a different network](remote-test-connection.md) together.
On that page, **You means Pranit** and **Friend means Om**. The connection steps are the same
for Codex and Claude Code; no Claude installation is needed.

It explains Tailscale, sharing Pranit's computer with Om, and an SSH tunnel. An **SSH tunnel**
forwards requests between the computers without making the API public.

**Finish that page before Step 4.** Om must be able to open this address in a Windows browser:

```text
http://127.0.0.1:18000/health/live
```

**Success:** it shows `{"status":"ok"}`. Keep Om's tunnel PowerShell window open.
Pranit's computer must stay awake, connected, and running Docker throughout the test.

## Step 4 — Om: prepare the repo and service token

Open a **second PowerShell window**; leave the tunnel window open.
If you have not cloned the repo:

```powershell
cd "$env:USERPROFILE\Documents"
git clone --branch develop https://github.com/Pranit-DC/ContextBridge.git
cd ContextBridge
```

If you already have the repo, open PowerShell in that folder instead. Run `git status --short`
and save unfinished changes before switching. Then run:

```powershell
git switch develop
git pull --ff-only origin develop
uv sync --frozen --python 3.12
```

**Do not start Docker or a second ContextBridge service on Om's computer.** Both Codex clients
must reach the same service and database.

Create a private adapter settings file for this test:

```powershell
if (-not (Test-Path .env.mcp.codex-test)) { Copy-Item .env.mcp.example .env.mcp.codex-test }
notepad .env.mcp.codex-test
```

**Pranit:** open `.env` privately and send **only** its `CONTEXTBRIDGE_API_TOKEN` value to Om
through a private channel. Do not send the database password, the whole `.env`, or Codex login
credentials. This service token grants access to all projects in your service; share it only
with a trusted tester.

**Om:** replace the file contents with these two lines, inserting the received token:

```dotenv
CONTEXTBRIDGE_API_URL=http://127.0.0.1:18000
CONTEXTBRIDGE_API_TOKEN=PASTE_PRANITS_CONTEXTBRIDGE_TOKEN_HERE
```

Save and close Notepad. The repo ignores this file; do not commit or screenshot its token.
Check the connection:

```powershell
$repo = (Get-Location).Path
& "$repo\.venv\Scripts\python.exe" -m contextbridge.mcp_adapter.cli --env-file "$repo\.env.mcp.codex-test" --project-id contextbridge-codex-test --agent-id codex-om --check
```

**Success:** `"status": "ready"`, the same project ID as Pranit, and `"agent_id": "codex-om"`.

## Step 5 — Pranit: register the MCP server in Codex

From the Linux repo terminal:

```bash
repo="$(pwd)"
codex mcp add contextbridge-codex-pair -- "$repo/.venv/bin/python" -m contextbridge.mcp_adapter.cli --env-file "$repo/.env.mcp" --project-id contextbridge-codex-test --agent-id codex-pranit
codex mcp list
```

**Success:** the list contains `contextbridge-codex-pair`.
This test name is separate from earlier `contextbridge` or `contextbridge-live` registrations.
If `codex` is not found, use the app settings method in Step 7 instead.

## Step 6 — Om: register the MCP server in Codex

From the second PowerShell window, in the Windows repo:

```powershell
$repo = (Get-Location).Path
codex mcp add contextbridge-codex-pair -- "$repo\.venv\Scripts\python.exe" -m contextbridge.mcp_adapter.cli --env-file "$repo\.env.mcp.codex-test" --project-id contextbridge-codex-test --agent-id codex-om
codex mcp list
```

**Success:** Om's list also contains `contextbridge-codex-pair`.
If `codex` is not found, use the app settings method below instead.

## Step 7 — Both: open a fresh local Codex chat

Open the desktop app and select/add **your own local ContextBridge repo folder** as a project.
Start a **new local Codex chat**, type `/mcp`, and check for `contextbridge-codex-pair`.
If it is missing, fully close/reopen the app and start another new chat.
Use a local Codex chat that can launch your adapter, rather than a cloud execution environment.

The desktop app and CLI share MCP settings on the same host. Registration commands and app
controls are explained in the [official OpenAI MCP documentation](https://learn.chatgpt.com/docs/extend/mcp).

**If the CLI command was unavailable:** open **Settings → MCP servers → Add server**,
name it `contextbridge-codex-pair`, and choose **STDIO**. STDIO means Codex starts the local
Python adapter as a process. Use your actual absolute paths in these fields:

| Field | Pranit | Om |
| --- | --- | --- |
| Command | `/home/pranitchiman/Projects/ContextBridge/.venv/bin/python` | `C:\Users\YOUR_WINDOWS_USER\Documents\ContextBridge\.venv\Scripts\python.exe` |
| Arguments | `-m contextbridge.mcp_adapter.cli --env-file /home/pranitchiman/Projects/ContextBridge/.env.mcp --project-id contextbridge-codex-test --agent-id codex-pranit` | `-m contextbridge.mcp_adapter.cli --env-file "C:\Users\YOUR_WINDOWS_USER\Documents\ContextBridge\.env.mcp.codex-test" --project-id contextbridge-codex-test --agent-id codex-om` |

Om should replace `YOUR_WINDOWS_USER` and use the real repo location if cloned elsewhere.
Quote paths with spaces in the arguments field. Save, select **Restart**, and start a new chat.
Keep credentials in the private env file; do not put the token in these fields.

If either Codex asks permission for a test tool call, approve that specific ContextBridge call.

## Step 8 — Both: confirm real tool access

Paste this into each person's new Codex chat:

```text
We are testing the ContextBridge MCP server named contextbridge-codex-pair.
Call its memory_status tool and show the returned result.
Use the actual MCP tool, not a shell request or a file. If the tool is unavailable or fails,
stop and show the error. Do not claim success without a tool result.
Do not edit project files during this test.
```

**Success:** both actual tool results say `status: ready` and `project_id: contextbridge-codex-test`.
Pranit's result must say `agent_id: codex-pranit`; Om's must say `agent_id: codex-om`.
Session IDs can differ. Check the tool results, not just the agent's summary.

## Step 9 — Pranit: make a new test label and save a decision

In the Linux terminal:

```bash
uv run python -c "import secrets; print('CBPAIR-' + secrets.token_hex(4))"
```

Example: `CBPAIR-a1b2c3d4`. This is **RUN_CODE**, a test label, not a password.
Replace `[RUN_CODE]` in every following prompt with your actual label.
Use a new label each time you repeat the test.

The **memory ID** identifies the saved record; the **version** counts revisions.
The agent generates a **UUID**, a unique request identifier. **Evidence** is your explicit
statement supporting the decision.

Paste into Pranit's Codex:

```text
Use only the contextbridge-codex-pair MCP tools for the memory operations below.
I explicitly authorize saving this test decision:
"[RUN_CODE]: We chose PostgreSQL for the test application."
Call memory_write with type DECISION, scope project, a fresh UUID request_id, and that exact content.
Use source.kind user, source.interaction "[RUN_CODE]-create", and my sentence above as source.evidence.
Do not add conditions or use developer-global scope. Do not edit files.
Show the returned memory ID and version. If the call fails, stop and show the error.
```

**Success:** the tool result contains a memory ID and version `1`. Record the ID for cleanup.
**Send Om only RUN_CODE** now. Do not send the saved decision, memory ID, or Codex response yet:
Om's next step should retrieve them from the service.

## Step 10 — Om: retrieve Pranit's decision

Paste into Om's Codex, replacing `[RUN_CODE]`:

```text
Using contextbridge-codex-pair, call memory_search with query "[RUN_CODE]" and scope project.
Show the returned memory ID, exact stored content, and version.
Do not guess the decision or read files to find it. If no memory is returned, say so and stop.
```

**Success:** the actual tool result has the PostgreSQL decision and version `1`.
Now compare the memory ID with Pranit's recorded ID; they must match.

## Step 11 — Om: change the same decision

Paste into the same Codex chat, replacing `[RUN_CODE]`:

```text
I explicitly change our test decision to:
"[RUN_CODE]: We chose SQLite for the test application."
Using contextbridge-codex-pair, inspect the memory found in the previous step.
Then call memory_update on that same memory ID, using its current version as expected_version.
Use the exact new sentence as content, source.kind user, source.interaction "[RUN_CODE]-update",
and my explicit change above as source.evidence.
Do not create a second memory or edit files. Show the returned ID and new version.
If a call fails, stop and show the error.
```

**Success:** the same memory ID now has SQLite content and version `2`.

## Step 12 — Pranit: verify from a fresh Codex chat

Start a **new local Codex chat** in your ContextBridge project. Do not tell it Om's new decision.
Paste this, replacing `[RUN_CODE]`:

```text
Using contextbridge-codex-pair, call memory_search with query "[RUN_CODE]" and scope project.
Then call memory_inspect on the returned memory ID.
Show the current stored decision, its version, both history entries, and their source.agent values.
Use only the actual MCP results. Do not guess or read files. Stop if any call fails.
```

**Success:** SQLite is current at version `2`; history retains PostgreSQL at version `1`.
The create source is `codex-pranit` and the update source is `codex-om`.
This checks that the change is stored outside the original chats.

## Step 13 — Pranit, then Om: delete and verify

Pranit pastes into Codex, replacing `[MEMORY_ID]` with the ID recorded in Step 9:

```text
I explicitly authorize forgetting only the test memory with ID [MEMORY_ID].
Using contextbridge-codex-pair, call memory_forget for that exact memory_id and show the tool result.
Do not delete any other memory and do not recreate this one.
```

After that succeeds, Om pastes into Codex, replacing both placeholders:

```text
Using contextbridge-codex-pair, call memory_search with query "[RUN_CODE]" and scope project.
Also call memory_inspect with memory_id "[MEMORY_ID]".
Show both tool results. Do not recreate the memory.
```

**Success:** search returns no matching memory; inspection reports that it was not found.
Forget removes the stored memory, history, and evidence. Chat transcripts, screenshots, and
existing database backups/recovery records have separate retention; forgetting does not erase them.

## Step 14 — Both: record results and disconnect

Copy this checklist into your team notes. Mark **PASS** only after checking actual tool results.
Record RUN_CODE, memory ID, date, operating systems, and each repo commit (`git rev-parse HEAD`).
Keep API tokens and SSH private keys out of notes and screenshots.

| Check | PASS / FAIL | Required result |
| --- | --- | --- |
| Both Codex clients connected | | Same project; `codex-pranit` and `codex-om` |
| Pranit saved the decision | | Memory ID, PostgreSQL, version 1 |
| Om retrieved it | | Same ID, PostgreSQL, version 1 |
| Om changed it | | Same ID, SQLite, version 2 |
| Fresh Pranit chat saw history | | Both versions and the two source labels |
| Om verified forgetting | | Empty search and not-found inspection |

If every row passes, record **Codex-to-Codex shared-memory test: PASS**.
Keep the Codex + Claude Code test marked **pending** until it is actually performed.
Automatic capture and semantic search are also outside this test; they are not implemented yet.

Om presses `Ctrl+C` in the tunnel window. Follow the connection page's cleanup steps for Om's
key and machine share. Optionally remove only this test registration on each computer:

```text
codex mcp remove contextbridge-codex-pair
```

Pranit can leave the service running or stop it without deleting database data:

```bash
docker compose down
```

## If something fails

| Problem | What to do |
| --- | --- |
| `uv` or Git is not found | Install the missing tool and reopen the terminal; see [uv installation](https://docs.astral.sh/uv/getting-started/installation/). |
| `codex` is not found | Use the desktop app settings method in Step 7. |
| Docker cannot connect | Start Docker and check `docker info` again on Pranit's computer. |
| Database port is occupied | In Pranit's `.env`, change `CONTEXTBRIDGE_DB_PORT` and the matching port in `CONTEXTBRIDGE_DATABASE_URL`, then rerun Compose. Default host port is 5433. |
| `migrate` exits with an error | Run `docker compose logs --no-color --tail=100 migrate`; keep credentials private when sharing logs. |
| Om cannot open `/health/live` | Follow the connection page's troubleshooting. Keep the tunnel open and Pranit's PC awake. |
| Health page works, but adapter fails authentication | Om's token must match Pranit's service token; Om's API URL must use the tunnel port, normally 18000. |
| Test server already exists | Run `codex mcp get contextbridge-codex-pair`. To replace only this entry, run `codex mcp remove contextbridge-codex-pair`, then repeat registration. |
| Chat cannot see the MCP server | Check it is enabled in Settings, restart, and start a new local Codex chat. Use native Windows paths with Windows Codex; do not mix in WSL paths. |
| Both results show the same agent ID | Check the registration's `--agent-id`; Pranit uses `codex-pranit`, Om uses `codex-om`. Restart the server/chat after correcting it. |
| Om retrieves nothing | Compare project IDs and RUN_CODE. Check both adapters reach Pranit's service, not two separate databases. |
| Agent says it worked but shows no tool call | Ask it to call the named MCP tool and display the result. Leave the step unpassed. |
| Update reports a version conflict | Inspect the ID again and use its current version. Do not create another memory. |

If the test stops after creation, keep the memory ID and perform Step 13 when the connection
works again. Do not delete database volumes to clean up a single test memory.
