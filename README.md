# ContextBridge

Save useful decisions once and retrieve them from different coding assistants.
ContextBridge keeps memories and their evidence in a shared local service, outside any one chat.

**New here?** Start with the [plain-language user guide](docs/user-guide.md).
For all documentation, use the [documentation index](docs/README.md).

## How it works

1. **Save:** add a memory yourself or enable supported Codex message capture.
2. **Store:** ContextBridge keeps accepted facts with their original evidence.
3. **Retrieve:** another connected assistant uses memory tools to find them.

Connecting an assistant does not automatically save its chats. Codex capture is a separate,
optional hook for future user messages. Automatic Copilot capture is not implemented.

## Quickstart: run from source

You need Git, [uv](https://docs.astral.sh/uv/), Node.js/npm, and running Docker with Compose.
Linux AI setup also needs an unlocked desktop Secret Service credential store.
Open a terminal in the ContextBridge installation folder, then run each command in order.
These commands work in fish, Bash, and PowerShell:

```text
uv sync --frozen --extra product --python 3.12
npm --prefix frontend ci
npm --prefix frontend run build
uv run --extra product contextbridge start
```

The first command installs the saved Python dependency versions. The second installs UI
packages, replacing frontend/node_modules. The third builds the UI. The last starts the local
manager and opens a private browser page. Keep the launcher running; keep its launch link private.
Prebuilt releases already contain UI assets and do not need the npm commands.

## First use

1. In **Settings → Services**, review the confirmation and choose **Start memory-only services**
   to begin with manual saves and exact-word search. Provider keys are unnecessary for this mode.
2. For automatic processing, use **Settings → Providers**: configure Groq, select the processing
   project, and save. **Meaning search** is optional and requires Cloudflare's token and account ID.
3. In **Settings → Services**, confirm and **Apply saved settings** to start with AI settings.
4. In **Connections**, generate memory-tool instructions for your agent. Optional Codex capture
   is configured separately on that screen.

The [user guide](docs/user-guide.md) explains each option, service state, and common recovery step.

## Start again or stop

From the installation folder:

```text
uv run --extra product contextbridge start
uv run --extra product contextbridge status
uv run --extra product contextbridge stop
```

Run only the command you need: start opens the UI, status reports state, and stop stops services
while keeping stored memories. Closing the browser does not stop services.
After UI source changes, rebuild the frontend, stop the old launcher with Ctrl+C, and start again.
Default ports: workspace 8501, memory API 8000, PostgreSQL 5433.

## Where to go next

| Need | Read |
| --- | --- |
| Understand the app and settings | [User guide](docs/user-guide.md) |
| Record cross-agent sharing | [Step-by-step demo](docs/cross-ide-linux-test.md) |
| Installation and credential recovery | [Local product](docs/local-product.md) |
| Development, API and required tests | [Developer reference](docs/development.md) |
| Architecture and team work | [Architecture](docs/architecture.md), [team plan](docs/team-plan/README.md) |
| Current implementation and limits | [V1 completion report](docs/v1-completion.md) |

The current product is local and single-user. Hosted processing sends selected text to configured
providers. Actual host compatibility and general model quality need separate verification;
implementation and offline test passes do not establish universal compatibility.
