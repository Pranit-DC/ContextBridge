# Inspection viewer (H3)

A small Streamlit page to see what the assistants remember: browse a project's memories, search by
words, read the full evidence and version history, correct a memory, and delete it permanently.
It talks to the service over HTTP only and has no database access.

## Status

| Part | State |
| --- | --- |
| `HttpViewerClient` (search, browse, inspect, correct, forget, status) | Implemented |
| Display models and `ViewerController` (every screen state in plain language) | Implemented |
| Streamlit app | Implemented |
| Streamlit as a project dependency and a launch entry point | **Pending**: Pranit owns `pyproject.toml` and `uv.lock` |
| Manual walkthrough in a real browser; accessibility review | **Not done** |
| Teammate clean-install walkthrough (H4) | Not done |

## Run it

Start the service as in the main README, then, until Streamlit is added to the project:

```text
uv run --with streamlit streamlit run src/contextbridge/inspection/app.py
```

In the sidebar enter the service address (local addresses only), the project, and the access token.
The token can also come from `CONTEXTBRIDGE_API_TOKEN` and the project from
`CONTEXTBRIDGE_PROJECT_ID`; a token taken from the environment is never sent to the browser.

**Windows with Docker Desktop:** use `127.0.0.1`, not `localhost`, in `CONTEXTBRIDGE_DATABASE_URL`.
`localhost` tries IPv6 first, and the database is published on IPv4 only, so every connection
waits about 8 seconds. The service then times out and tests appear to hang. See the
[integration request](integration-request.md).

## What you can do

- **Browse:** every memory in the selected project, a page at a time. This is the real listing; an
  empty search is not.
- **Search:** matches the words you type, with an option to include memories that apply to all
  your projects and one optional condition. It does not guess related meanings.
- **Details:** the current version, every earlier version, the evidence for each, and plain
  sentences such as "Version 2 replaced version 1."
- **Correct:** needs the corrected text and where it comes from. The earlier version is kept.
- **Delete:** needs a ticked confirmation, then removes the memory, its history, and its evidence.

Disputed memories and lower-confidence ones (below 0.7) say so on their card.

## Safety behavior

- **Project boundary.** The client is bound to the selected project. Any ID operation reads the
  memory first and treats another project's memory as not found, so a change or delete for it is
  never sent, and its project name is not revealed. Search and browse refuse results outside the
  selection. This boundary lives in the viewer: the service token itself covers all of the
  developer's projects.
- **Stale corrections.** Streamlit re-runs on every click, so the version you opened is remembered.
  If the memory changes while you read it, the form is disabled until you choose to review the
  latest version. If a save still races the change, the service rejects it once, you see the newer
  version, and your text is restored. Nothing is retried automatically.
- **Literal text.** Everything from the service is shown with `st.text`, with control and
  direction-override characters removed, so content is never read as HTML or markdown.
- **Privacy.** No Streamlit cache is used and nothing is logged. Session state holds only the
  selected ID, the version you opened, and what you typed. Restarting the viewer erases nothing,
  because the service owns the data.
- **Errors.** Failures show one of a few fixed messages (unavailable, token rejected, not found,
  changed, invalid, unexpected). No response body, input, or credential is ever copied into one.
- **Remote services.** Only local addresses are accepted by default, and a remote service needs an
  explicit opt-in and `https`.

## Tests and results

Reported separately, because they prove different things.

| Check | Command | Result |
| --- | --- | --- |
| Client, display models, controller against **fake HTTP** | `uv run pytest tests/inspection` | 109 passed |
| Streamlit screens (AppTest) against **fake HTTP** | `uv run --with streamlit pytest tests/inspection/test_app.py` | 15 passed (skipped when Streamlit is absent) |
| Client and controller against the **real service and PostgreSQL** | `uv run python scripts/inspection/real_api_check.py --env-file .env` | 28 of 28 passed |
| Streamlit screens against the **real service and PostgreSQL** | ad hoc AppTest run, not committed | 8 of 8 passed |

The real-service script writes throwaway memories under its own project IDs, removes them, and
should be pointed only at a disposable local service. Not yet covered: a human using a real
browser, and an accessibility review.

## Known limits

- Search is lexical. It is not semantic or hybrid, and the viewer does not claim otherwise.
- Pagination comes from the service and is not a snapshot: concurrent changes can alter pages.
- Token rotation invalidates open page cursors; the viewer then shows a notice.
- Related-memory and verification labels from the retrieval module are not shown here yet; they
  need the planned retrieval endpoint.
