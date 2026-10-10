# Test ContextBridge with real Codex and Claude Code

This guide is for **you on Linux with Codex** and **your friend on Windows with Claude Code**,
even when you are on different networks. Send your friend this page and the linked connection page.

If your available teammate is Om and you both have Codex, use the
[Pranit + Om Codex guide](live-codex-test.md) instead.

**The goal:** Codex saves a test decision on your computer. Claude Code finds and changes that
same decision. Codex sees the change and its history. You then delete only that test decision.

Only **your computer** runs the ContextBridge service and database. Your friend connects to it.
Starting a second database on your friend's computer would give you two separate sets of memories.

## Before starting

| Person | Needs |
| --- | --- |
| You | The repo, Git, uv, running Docker, and Codex with a working login |
| Friend | The repo, Git, uv, and Claude Code with a working login; Docker is not needed for this test |
| Both | Internet, Tailscale accounts for the different-network connection, and this guide |

Each person uses their own agent account. ContextBridge itself needs no LLM API key for this test.
Its **API token** is a password for accessing ContextBridge, separate from your agent's login.
**MCP** is the connection that lets the agent call ContextBridge's tools.

Follow the steps in order. Commands go in a terminal; prompts go in the agent's chat.
If a step fails, use the troubleshooting section before continuing.

## Step 1 — You: open the repo and check the tools

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

**Success:** you are on `develop`, uv shows a version, and Docker shows information instead of
a connection error. Docker must stay running throughout the test.

## Step 2 — You: start ContextBridge

In the same terminal, run each line and wait for it to finish:

```bash
uv sync --frozen --python 3.12
uv run python scripts/setup_local.py --project-id contextbridge-live-test
docker compose up --build -d
docker compose ps -a
```

Setup creates missing credential files for you. It keeps existing credentials.
In the container list, look for:

- `db`: **healthy**.
- `migrate`: **Exited (0)**. This is normal: it has finished preparing the database.
- `api`: **Up**.

Now check the adapter's connection:

```bash
repo="$(pwd)"
uv run python -m contextbridge.mcp_adapter.cli --env-file "$repo/.env.mcp" --project-id contextbridge-live-test --agent-id codex --check
```

**Success:** the output includes `"status": "ready"` and `"project_id": "contextbridge-live-test"`.
If it says authentication failed, open `.env` and `.env.mcp` in your editor and make their
`CONTEXTBRIDGE_API_TOKEN` values match. Do not generate a new token just to repeat the test.

## Step 3 — Both: connect your computers

Follow [Connect a friend on a different network](remote-test-connection.md) together.
It explains Tailscale and the SSH tunnel, including which commands each person runs.

**Finish that page before Step 4.** Your friend should be able to open
`http://127.0.0.1:18000/health/live` on Windows and see `{"status":"ok"}`.
Keep the friend's tunnel terminal open. Your Linux computer must stay awake and online.
`127.0.0.1` means "this computer"; the tunnel makes the friend's local port reach your service.

## Step 4 — Friend: prepare the repo and access token

Open a **second PowerShell window**, leaving the tunnel window open.
If you have not cloned the repo, run:

```powershell
cd "$env:USERPROFILE\Documents"
git clone --branch develop https://github.com/Pranit-DC/ContextBridge.git
cd ContextBridge
```

If you already cloned it, open PowerShell in that folder instead. Check for unfinished changes
with `git status --short`; save them before switching. Then run:

```powershell
git switch develop
git pull --ff-only origin develop
uv sync --frozen --python 3.12
```

Create a separate settings file for this test:

```powershell
if (-not (Test-Path .env.mcp.live-test)) { Copy-Item .env.mcp.example .env.mcp.live-test }
notepad .env.mcp.live-test
```

**You:** open your `.env` privately in your editor. Send only its API token to your trusted friend
through a private channel. Do not send the database password, the whole `.env`, or agent account
credentials. This token accesses all projects in your service; share it only with a trusted tester.

**Friend:** make your `.env.mcp.live-test` contain these two lines, replacing the token placeholder:

```dotenv
CONTEXTBRIDGE_API_URL=http://127.0.0.1:18000
CONTEXTBRIDGE_API_TOKEN=PASTE_THE_CONTEXTBRIDGE_TOKEN_YOU_RECEIVED
```

Save the file and close Notepad. Keep this file out of Git; the repo already ignores it.
Your friend's file points to the tunnel, not to a separate service.

Check the connection in PowerShell:

```powershell
$repo = (Get-Location).Path
& "$repo\.venv\Scripts\python.exe" -m contextbridge.mcp_adapter.cli --env-file "$repo\.env.mcp.live-test" --project-id contextbridge-live-test --agent-id claude-code --check
```

**Success:** `"status": "ready"`, the same project ID as yours, and `"agent_id": "claude-code"`.

## Step 5 — You: connect Codex

From the Linux repo terminal:

```bash
repo="$(pwd)"
codex mcp add contextbridge-live -- "$repo/.venv/bin/python" -m contextbridge.mcp_adapter.cli --env-file "$repo/.env.mcp" --project-id contextbridge-live-test --agent-id codex
codex mcp list
```

**Success:** the list contains `contextbridge-live`.
This name keeps the test registration separate from any existing `contextbridge` registration.

Open the desktop app, select/add your ContextBridge folder as a project, and start a **new local
Codex chat**. Type `/mcp` and check for `contextbridge-live`. If it is missing, fully close and
reopen the app, then start a new chat. The CLI and desktop share the MCP configuration on the
same host. These setup controls are described in the [official OpenAI MCP guide](https://learn.chatgpt.com/docs/extend/mcp).

If `codex` is not found in your terminal, use the app's **Settings → MCP servers → Add server**
instead: name `contextbridge-live`, type **STDIO**, command your repo's `.venv/bin/python`, and
arguments `-m contextbridge.mcp_adapter.cli --env-file /YOUR/ABSOLUTE/REPO/.env.mcp --project-id contextbridge-live-test --agent-id codex`.
Use your real absolute paths, save, and restart. If your path contains spaces, quote it in the
arguments field. Keep credentials in `.env.mcp`, not in the command.

## Step 6 — Friend: connect Claude Code

From PowerShell in the Windows repo:

```powershell
$repo = (Get-Location).Path
claude mcp add --transport stdio --scope local contextbridge-live -- "$repo\.venv\Scripts\python.exe" -m contextbridge.mcp_adapter.cli --env-file "$repo\.env.mcp.live-test" --project-id contextbridge-live-test --agent-id claude-code
claude mcp list
claude
```

In Claude Code, type `/mcp` and check that `contextbridge-live` is connected.
Use Claude **Code**, not the ordinary claude.ai website. Start Claude from this repo folder:
the registration is saved for that folder. See [Claude Code's official MCP instructions](https://code.claude.com/docs/en/mcp).

If either agent requests tool permission, approve the specific ContextBridge call for this test.

## Step 7 — Both: check the connection inside the real agent

Paste this prompt into **each agent**, once:

```text
We are testing the ContextBridge MCP server named contextbridge-live.
Call its memory_status tool and show the returned result.
Use the actual MCP tool, not a shell request or a file. If the tool is unavailable or fails,
stop and show the error. Do not claim success without a tool result.
Do not edit project files during this test.
```

**Success:** both agents return `status: ready` and `project_id: contextbridge-live-test`.
Your agent ID is `codex`; your friend's is `claude-code`. Session IDs can be different.
Look at the tool-call/result in the chat, not just the agent's statement that it worked.

## Step 8 — You: choose a new test label

In the Linux terminal:

```bash
uv run python -c "import secrets; print('CBLIVE-' + secrets.token_hex(4))"
```

Example output: `CBLIVE-a1b2c3d4`. Call this your **RUN_CODE**.
It is a label, not a password. Replace `[RUN_CODE]` in every prompt below with your actual label.
Use a new label each time you repeat the whole test.

## Step 9 — You: ask Codex to save a decision

The **memory ID** identifies the saved record; its **version** counts its revisions.
The agent generates a **UUID**, a unique request identifier, for you. **Evidence** is the user
statement that supports the saved decision.

Paste into Codex, after replacing `[RUN_CODE]`:

```text
Use only the contextbridge-live MCP tools for the memory operations below.
I explicitly authorize saving this test decision:
"[RUN_CODE]: We chose PostgreSQL for the test application."
Call memory_write with type DECISION, scope project, a fresh UUID request_id, and that exact content.
Use source.kind user, source.interaction "[RUN_CODE]-create", and my sentence above as source.evidence.
Do not add conditions or use developer-global scope. Do not edit files.
Show the returned memory ID and version. If the call fails, stop and show the error.
```

**Success:** a tool result contains a memory ID and version `1`.
Record the ID for later cleanup. **Send your friend only RUN_CODE** at this stage, not the decision
or Codex's answer. This makes the next step prove retrieval rather than copying your message.

## Step 10 — Friend: retrieve what Codex saved

Paste into Claude Code, replacing `[RUN_CODE]`:

```text
Using contextbridge-live, call memory_search with query "[RUN_CODE]" and scope project.
Show the returned memory ID, exact stored content, and version.
Do not guess the decision or read files to find it. If no memory is returned, say so and stop.
```

**Success:** Claude's actual tool result contains the PostgreSQL decision, version `1`, and the
same ID that Codex returned. Now compare the IDs together.

## Step 11 — Friend: change the same decision

Paste into the same Claude Code session:

```text
I explicitly change our test decision to:
"[RUN_CODE]: We chose SQLite for the test application."
Using contextbridge-live, inspect the memory found in the previous step.
Then call memory_update on that same memory ID, using its current version as expected_version.
Use the exact new sentence as content, source.kind user, source.interaction "[RUN_CODE]-update",
and my explicit change above as source.evidence.
Do not create a second memory or edit files. Show the returned ID and new version.
If a call fails, stop and show the error.
```

**Success:** the same memory ID now has version `2` and SQLite content.

## Step 12 — You: check the change and history from a fresh Codex chat

Start a **new Codex chat** in the same local project. Do not tell it what Claude changed.
Paste this, replacing `[RUN_CODE]`:

```text
Using contextbridge-live, call memory_search with query "[RUN_CODE]" and scope project.
Then call memory_inspect on the returned memory ID.
Show the current stored decision, its version, both history entries, and their source.agent values.
Use only the actual MCP results. Do not guess or read files. Stop if any call fails.
```

**Success:** the current decision says SQLite at version `2`; the history retains PostgreSQL at
version `1`. The first source is `codex`, and the correction source is `claude-code`.
The fresh chat verifies that the memory survives outside the original conversation.

## Step 13 — You, then Friend: delete only the test memory

In Codex, paste this, replacing `[MEMORY_ID]` with the ID you recorded:

```text
I explicitly authorize forgetting only the test memory with ID [MEMORY_ID].
Using contextbridge-live, call memory_forget for that exact memory_id and show the tool result.
Do not delete any other memory and do not recreate this one.
```

Then your friend pastes into Claude Code, replacing both placeholders:

```text
Using contextbridge-live, call memory_search with query "[RUN_CODE]" and scope project.
Also call memory_inspect with memory_id "[MEMORY_ID]".
Show both tool results. Do not recreate the memory.
```

**Success:** search returns no matching memory, and inspection reports that it was not found.
Deletion removes the stored memory and its stored history/evidence. Chat messages and screenshots
are separate copies; this operation does not erase them.

## Step 14 — Both: record the result and close the connection

Copy this table into your team notes. Mark **PASS** only when the actual tool result matched.
Include RUN_CODE, memory ID, date, each operating system, and the tested commit (`git rev-parse HEAD`).
Keep API tokens and SSH private keys out of notes/screenshots.

| Check | PASS / FAIL | What to record |
| --- | --- | --- |
| Both real agents connected | | Two `memory_status` results |
| Codex saved the decision | | ID, version 1 |
| Claude retrieved it | | Same ID and PostgreSQL content |
| Claude corrected it | | Same ID, SQLite, version 2 |
| Fresh Codex chat saw history | | Both versions and source agents |
| Forget was verified from Claude | | Empty search and not-found inspection |

Take screenshots of the tool results if needed for your presentation. If all rows pass, the
**real-agent shared-memory test passes**. This does not prove automatic capture or semantic search;
those features are still pending.

Friend: press `Ctrl+C` in the SSH tunnel window. Follow the connection page's cleanup steps.
You can leave ContextBridge running. To stop it without deleting its data:

```bash
docker compose down
```

## If something fails

| Problem | What to do |
| --- | --- |
| `uv`, Git, or Claude is not found | Install the missing tool, then reopen the terminal. Use [uv installation](https://docs.astral.sh/uv/getting-started/installation/) and [Claude Code setup](https://code.claude.com/docs/en/setup). |
| Docker cannot connect | Start Docker; check `docker info` again. |
| Database port is occupied | In your `.env`, change `CONTEXTBRIDGE_DB_PORT` and the matching port in `CONTEXTBRIDGE_DATABASE_URL`, then rerun Compose. Default host port is 5433. |
| `migrate` exits with an error | Read `docker compose logs --no-color --tail=100 migrate`; keep credentials private in shared logs. |
| Friend cannot open `/health/live` | Check the tunnel window and the connection page. Keep your PC awake. |
| `/health/live` works but adapter authentication fails | Friend's token must equal your service token; friend's URL must use port 18000. |
| Server is already registered | Check its command with `codex mcp get contextbridge-live` or `claude mcp get contextbridge-live`. To replace only this test entry, remove it (`codex mcp remove contextbridge-live` / `claude mcp remove --scope local contextbridge-live`) and repeat registration. |
| Tool is missing in the chat | Check `/mcp`, enable the server, and start a fresh local session. Claude must be launched from the registration folder. |
| Claude finds nothing | Compare `memory_status` project IDs and verify the same RUN_CODE. Do not create a second service on Windows. |
| Agent answers but shows no tool call | Ask it to call the named MCP tool and show the result. Do not mark that step as passed yet. |
| Update reports a version conflict | Inspect the ID again. Use the current version; do not create a replacement memory. |

If a test stops after saving the decision, keep its ID and perform Step 13 once the connection
works again. Do not delete the database volume to clean up one test memory.

## If both agents later run on your Linux computer

Skip the different-network connection. Register Claude from the same Linux repo instead:

```bash
repo="$(pwd)"
claude mcp add --transport stdio --scope local contextbridge-live -- "$repo/.venv/bin/python" -m contextbridge.mcp_adapter.cli --env-file "$repo/.env.mcp" --project-id contextbridge-live-test --agent-id claude-code
claude
```

Then use the same agent prompts. Both accounts need working access on that computer for this route.
