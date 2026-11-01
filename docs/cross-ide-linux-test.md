# Demo walkthrough: Codex → ContextBridge → VS Code Copilot

**Goal:** say a decision in Codex, show its saved evidence in ContextBridge,
then retrieve it in a fresh Copilot chat.

Use your Linux desktop for both apps. Preparation includes a few **fish-compatible**
commands and one configuration file. **The recording itself needs no terminal.**
Do steps 1–7 before recording. If something is already working, skip that step.

## 1. Open the ContextBridge project

1. Open your Linux file manager. Find the folder containing ContextBridge's
   `README.md`, `pyproject.toml`, and `frontend` folder. This is the installation
   folder; it can be anywhere on your machine.
2. Open that folder in VS Code using **File → Open Folder**.
3. Choose **Terminal → New Terminal**. Use your fish terminal.
4. Confirm the terminal is in that folder. If unsure, type `pwd`: it only prints
   your current folder. Do not run the following commands from another folder.

You need uv, Node/npm, Docker with Compose, signed-in Codex, and working Copilot.
Open Docker Desktop if you use it. If a command below says “not found”, install
that prerequisite before continuing; this guide does not install system software.

## 2. Start ContextBridge

If the current ContextBridge page already works, skip to step 3.
Otherwise, run these **one at a time** in the installation folder:

```fish
uv sync --frozen --extra product --python 3.12
```

Installs the project's Python packages using the saved dependency versions.
It can download packages and Python; it does not save demo memories.

```fish
npm --prefix frontend ci
```

Installs the UI packages from the lockfile, replacing `frontend/node_modules`.

```fish
npm --prefix frontend run build
```

Builds the browser interface. Wait for it to finish successfully.

```fish
uv run --extra product contextbridge start
```

Starts the local manager and opens its private browser page. Keep this terminal
open. Do not share its launch link. If any step fails, resolve the displayed
error before moving on; restarting commands blindly will not fix missing setup.

## 3. Make an empty demo workspace

1. In your file manager, create an empty folder named **ContextBridgeDemo**
   wherever you prefer, for example inside Documents.
2. Open it and copy its full location from the file manager's location bar
   (**Ctrl+L**, then **Ctrl+C** in many Linux file managers).
3. Keep that location handy. This is the **demo workspace**, not the installation folder.
4. Open this demo folder in a **new VS Code window** using **File → New Window**,
   then **File → Open Folder**. Keep the installation terminal running.

## 4. Choose the project and enable processing

In the ContextBridge browser page:

1. Open **Current project → Open another project…** and use `demo-video-01`.
   Use this exact project ID throughout the setup.
2. Open **Settings**. Enable **AI processing**.
3. Configure your Groq API key and a supported processing model. If a working
   key is already saved, keep it. Confirm the Free-plan checkbox only if true.
4. **Meaning search is optional.** Leave it off for less setup, or keep it on if
   Cloudflare is already configured. The exact-word lookup below works without it.
5. Under **Capture project**, choose **Processing project** as
   `demo-video-01`. Leave the Advanced defaults unchanged for this demo.
6. Click **Save secure settings**. Open **2. Services**, review the restart consent, then click
   **Apply saved settings**. This restarts services; wait for them to be ready.

Use invented data: processing sends selected text to your hosted provider and
uses its quota. On Linux, the OS credential store must be unlocked to save keys.
**Start memory-only services** cannot demonstrate automatic AI extraction.

## 5. Connect VS Code Copilot

1. In ContextBridge, open **Connections** and click **Connection instructions**.
2. Click **Copy VS Code configuration**. It already contains this machine's paths and selected project.
3. In the **demo folder's VS Code window**, create `.vscode` with the Explorer's
   **New Folder** button, then create `mcp.json` inside it with **New File**.
4. Paste the copied configuration into that file. Save with **Ctrl+S**.
5. If this file already contains other servers, add the generated server under
   its existing `servers` object instead of replacing the file.
6. Press **Ctrl+Shift+P**, run **MCP: List Servers**, select
   **contextbridge-demo**, then **Start**. Review the trust prompt.
7. Open Copilot Chat in an agent session with tools enabled. Enable the
   `contextbridge-demo` tools in its tools picker if necessary.
8. Send:

   > Use contextbridge-demo to call memory_status. Show its project and status.

**Continue only when the actual tool result says ready and `demo-video-01`.**
If it fails, check the server's output through **MCP: List Servers**.
The configuration format and server controls follow the
[VS Code MCP reference](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).

## 6. Enable automatic capture from Codex

1. In ContextBridge **Connections → Codex message capture**, paste the full
   **demo workspace** location from step 3.
2. Click **Preview hook**. Review the change and select the approval checkbox.
3. Click **Enable capture**. This adds ContextBridge's hook to that workspace.
4. In Codex, open that **same demo folder** and start a fresh chat.
5. Complete your Codex client's normal hook trust/approval flow if prompted.

Your Codex client must support and load the workspace hook. Installing a hook
alone does not prove it is running. If your client does not support it,
automatic capture cannot be demonstrated in that client.

## 7. Rehearse before recording

1. In Codex, send a made-up decision, such as:

   > This project's rehearsal codename is Paper Kite. Just acknowledge it.
   > Do not save it manually or call memory_write.

2. In ContextBridge **Activity**, refresh until processing finishes.
3. Open **Memories → Browse memories**. Find the rehearsal decision and open
   its evidence. Confirm your original statement appears.
4. In Copilot, ask it to search ContextBridge for **rehearsal codename** and
   inspect the result. Confirm the memory ID matches the UI.

If the hook queues a message but no memory appears, inspect Activity's failure
reason and fix processing before recording. Queued does not mean saved.

## 8. Record: say a new decision in Codex

Start your screen recorder. In a fresh Codex chat in the same demo folder, send:

> Our project's release codename is Cedar Lantern. Just acknowledge it.
> Do not save it manually or call memory_write.

Use a different codename if you have already used this one. Do not put the
answer in a shared file or in Copilot's question.

## 9. Record: show the captured memory

1. Switch to ContextBridge **Activity** and refresh until processing finishes.
2. Open **Memories → Browse memories**.
3. Open the new decision. Show its content, original evidence, and memory ID.

Say: **“ContextBridge captured my message from Codex and stored the decision
with its original evidence.”** Only say this after the record actually exists.

## 10. Record: retrieve it in Copilot

1. Switch to VS Code Copilot and start a **fresh chat**.
2. Enable the demo server's tools. Send:

   > Use only contextbridge-demo. Search for “release codename”, then inspect
   > the matching memory. Show its codename, original evidence, and memory ID.
   > Do not read workspace files or use another memory tool.

3. Expand the tool results. Show that the codename and memory ID match
   ContextBridge's record.

Say: **“Copilot retrieved the same decision through ContextBridge in a different
client.”** Stop recording. That is the complete demo.

## 11. Finish

In ContextBridge **Connections**, review the consent and **Pause capture** if
you do not want future prompts captured. Stop the demo MCP server if desired.
Keep existing memory volumes; do not delete other projects' memories.

## What is automatic today?

- Connecting through MCP alone does **not** save chats. A save requires a
  `memory_write` tool call, usually following your request.
- An enabled, trusted Codex capture hook submits **future user messages**
  automatically. Processing can fail or reject them. Old chats and assistant
  replies are not captured.
- Copilot can read/write through tools. Automatic Copilot chat capture is not
  implemented. Retrieval also needs a tool call.

If automatic capture cannot run, use **Add memory** and demonstrate Copilot
retrieval. Call that **manual save and sharing**, not automatic capture.
