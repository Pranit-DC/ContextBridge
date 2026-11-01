# ContextBridge user guide

## What runs on your computer?

The **browser page** is the control panel. The **local services** store memories, answer agent
requests, and process messages. Opening the page does not mean those services are running.
**Docker** runs them in the background; you do not need to manage individual containers normally.

Your assistants connect to the memory service through **MCP**, a tool connection. That lets them
save or search when they call a tool. It does not automatically copy an entire chat.

## Start here

1. Follow [startup](../README.md#quickstart-run-from-source) once. Keep its launcher open.
2. Choose your project from **Current project** in the sidebar. Recent choices are remembered
   in this browser. Choose **Open another project…** only to add a name you have not used here.
   Switching clears workspace drafts, so review the warning before confirming.
3. Open **Settings**. Use one of the two modes below.
4. Use **Connections** to add memory tools to an assistant, then verify its project and status.

A project name is a memory label, not a folder path. Both assistants must use the same label.
The workspace folder is the real folder open in your editor; capture setup asks for that separately.

## Choose a mode

| Mode | What you can do | Needed |
| --- | --- | --- |
| Memory-only | Manually save, browse, inspect, and use exact-word memory search | Running local services |
| AI processing | Extract useful memories from captured or imported messages | Groq key, confirmed Free plan, matching processing project, running workers |
| Meaning search | Find related memories with different wording using richer retrieval | Cloudflare token and its separate account ID, indexing, running services |

Meaning search is optional, not discouraged. Enable it when you want that feature and have
configured Cloudflare. The simple exact-word demo can run without it. Tool support matters:
`memory_search` is keyword search; the richer `memory_retrieve` tool supports configured V1 retrieval.

## Settings → Providers

- **Enable AI processing:** sends selected captured/imported text to Groq to identify useful
  memories. Messages can be rejected or fail processing; queued is not the same as saved.
- **Processing model:** the Groq model used for extraction and reasoning.
- **Groq key action:** keep the saved key, add/replace it, or remove it. Keys are stored in your
  OS credential store. Removal disables the related feature when saved.
- **Groq Free-plan confirmation:** your declaration about the account; not a billing verification.
- **Enable meaning search:** enables Cloudflare indexing/retrieval by meaning.
- **Cloudflare account ID:** a 32-character identifier, separate from the API token. Both are needed.
- **Processing project:** choose an existing project from the dropdown. This controls which
  project's captured messages the processor accepts. Switching the sidebar only changes browsing.

**Save secure settings** stores preferences and keys. It does not start services.
Read any message beside a disabled save button: it explains what needs attention.
Changing keys pauses processing. After saving, open **Services** to apply the saved configuration.

**Check provider connections** makes a small online request after your explicit consent.
Save edits first: the checks use saved settings. Checks consume provider allowance and have a
cooldown/daily attempt limit. They do not start your local memory services.

## Settings → Services

1. Review what starting/restarting does. Select the confirmation checkbox.
2. Choose **Apply saved settings** to start/restart using saved AI settings, or
   **Start memory-only services** for manual saves without hosted AI.
3. Use **Refresh service status** to see the latest container state.

**Stop local services** stops the backend and keeps stored memory volumes.
Starting in memory-only mode does not erase your saved provider preferences.

| Status | Meaning |
| --- | --- |
| Services stopped | The browser can open, but agents cannot use stopped services |
| Running | That background component is running; it does not prove provider readiness |
| Not started | A container exists but has not started |
| Database setup: Completed | Normal: the one-time database preparation finished successfully |
| Database setup: Failed | Database preparation failed; review startup before continuing |
| Startup needs attention | The last start failed; refresh, check Docker, and resolve the reported error |

Use **Technical service details** only when troubleshooting. Keep memory volumes when recovering.

## Settings → Advanced

These controls are optional. Defaults work for an initial demo.

- **Daily token ceiling:** caps configured processing token allowance, not a guaranteed cash budget.
- **Group nearby interactions:** lets the system process nearby messages together. Its wait time
  and maximum group size apply only when grouping is enabled.
- **Consolidate in background:** periodically proposes combining compatible memories; uses AI quota.
- **Raw interaction retention:** how long source capture buffers remain, separate from durable memories.
- **Original timezones (V2):** supports explicitly imported evidence bundles, not wider chat capture.

## Connections

**Memory tools:** generate the ready-to-copy VS Code configuration, save it in the agent
workspace's `.vscode/mcp.json`, start its server, review trust, and enable its tools in Copilot.
Other compatible hosts use the displayed command and arguments. Verify using `memory_status`.
No provider keys are embedded in the generated configuration.

**Codex message capture:** enter the actual editor folder, preview the hook, review consent,
then enable it. Use the same processing project. Open a fresh session in a Codex client that
supports workspace hooks and complete its trust flow. Installed does not mean the host loaded it.
Only future user prompts are submitted; old chats and assistant/tool replies are not captured.
Copilot has no automatic capture integration here.

## Everyday screens

- **Overview:** how the system works, setup shortcuts, and service/configuration status.
- **Memories:** browse or search saved records. Open a record to inspect its evidence and history.
- **Add memory:** explicitly save something with evidence or import selected messages.
- **Activity:** review processing results. Open saved memories to confirm success; queueing alone
  is not proof of storage. Maintenance actions are available separately from routine activity.
- **About:** privacy and current limits.

Action feedback stays on screen; you do not need to scroll to the top. Errors remain until
dismissed or another action starts. Keep original evidence when correcting or restoring a memory.
Permanent deletion requires its own confirmation and does not erase copies in agent chats or providers.

## Common problems

| Problem | What to do |
| --- | --- |
| Checkbox checked but provider check refuses | Save first. The checkbox may be an unsaved draft; checks use saved settings |
| Save disabled | Read its nearby reason: unlock secure storage, migrate old keys, wait, or reload changed settings |
| Settings changed elsewhere | Review your draft before Reload saved settings; reload discards unsaved settings and entered keys |
| Database/queue stopped | Open Services, review confirmation, then apply/start. Saving alone does not start them |
| No captured memory | Check hook trust, project match, AI processing, workers, and Activity's reason |
| Copilot finds nothing | First verify a record exists, then confirm the same project and the enabled memory tools |

For installation recovery and exact platform limits, see [local product](local-product.md).
