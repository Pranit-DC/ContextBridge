# Integration requests to Pranit (viewer)

Nothing here has been changed outside `src/contextbridge/inspection/`, `tests/inspection/`,
`scripts/inspection/`, and `docs/inspection/`.

## 1. Streamlit dependency and launch entry point

The viewer imports `streamlit`, which is not in `pyproject.toml` or `uv.lock`. Please add it as an
**optional** group so the service and MCP adapter stay light, for example:

```toml
[project.optional-dependencies]
viewer = ["streamlit>=1.40,<2"]
```

and, if you want a launcher, a script such as `contextbridge-viewer` that runs
`streamlit run` on `contextbridge/inspection/app.py`. The app was tested with Streamlit 1.65.0.
Until then it runs with `uv run --with streamlit streamlit run src/contextbridge/inspection/app.py`,
and `tests/inspection/test_app.py` skips itself when Streamlit is not installed. Once the group
exists, CI could install it so those 15 screen tests run there too.

## 2. Windows: use 127.0.0.1 for the database, not localhost

On Windows with Docker Desktop, `localhost` resolves to IPv6 first while Compose publishes the
database only on `127.0.0.1`. Every connection then waits about 8 seconds before falling back.
Observed here: the API timed out on its first write, and the full test suite appeared to hang at a
PostgreSQL test. With `127.0.0.1` the same viewer check ran in 5 seconds. These shared files use
`localhost`:

- `.env.example` (line 6)
- `scripts/setup_local.py` (the `.env` it generates)
- `docs/windows-setup.md` and the `README.md` test-database example

Suggested: write `127.0.0.1` in those, or publish the port on `::1` as well. I worked around it
locally with an environment override and did not edit any `.env`.

## 3. What the viewer relies on (already implemented)

- `POST /v1/inspection/browse` with the contract's BrowseQuery and BrowseResult, project scope
  excluding developer-global records, and cursor errors returned as 422.
- `GET/PUT/DELETE /v1/memories/{id}`, `POST /v1/memories/search`, and `GET /health/ready` as today.
  The viewer treats `409` on `PUT` as a stale version.

## 4. Later

When `POST /v1/retrieval/search` exists, the viewer could show retrieval cards, including the
`verification` label and any "related memory" disclosure. That needs the card marker described in
[docs/retrieval/integration-request.md](../retrieval/integration-request.md).
