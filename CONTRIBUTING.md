# Contributing

Create a feature branch from the current `develop`; target every PR to `develop` and keep it
centered on one working behavior. The team handles stable releases to `main` manually.
Coordinate shared schemas/interfaces before implementation and integrate small changes regularly.
Prefer commits such as `feat: add scoped memory operations` or `fix: preserve conditional validity`.

Follow `AGENTS.md` and the README's checks. Include regression tests when a change can affect scope,
memory state, evidence, retrieval, retries, or deletion. Schema changes require reviewed migrations.
Dependency changes require an updated `uv.lock`. Never commit `.env`, tokens, or raw private sessions.

Before opening a PR, explain the user-visible behavior, what was tested, and what is still pending.
Do not merge without review and required checks. GitHub repository settings (branch protection,
review requirements, and access) are managed separately from source changes.
