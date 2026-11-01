# Documentation

Start with one guide for your task. Older implementation reports remain available as references.

## Use ContextBridge

- [User guide](user-guide.md): how the app works, settings, project selection, and errors.
- [Startup](../README.md#quickstart-run-from-source): install and run from source, including fish.
- [Local product](local-product.md): operating systems, credential storage, recovery, and limits.
- [Cross-agent demo](cross-ide-linux-test.md): prepare once, then record Codex → memory → Copilot.

## Develop and contribute

- [Developer reference](development.md): backend setup, API, checks, and historical V1 status.
- [Architecture](architecture.md) and [development plan](development-plan.md).
- [Team ownership and contracts](team-plan/README.md).
- [Agent/MCP integration](agent-integration.md), [capture/ingestion](ingestion.md),
  [background jobs](workers.md), and [memory lifecycle](memory-lifecycle.md).

## Evidence and historical interfaces

- [Current V1 report](v1-completion.md) and [remaining work](remaining-work.md).
- [UI screenshots](report/interface-screenshots.md) and [UX repair report](report/ux-recovery.md).
- [Legacy Streamlit workspace](local-workspace.md), [Linux V1 launcher](linux-v1.md),
  and [Windows setup](windows-setup.md) describe additional or earlier workflows.
- Formation, retrieval, research, team plans, and evaluation reports are technical references;
  they are not prerequisites for using the browser workspace.

The browser workspace is the default interface. Use its startup guide first rather than mixing
legacy launchers and manual Docker commands with the managed product.
