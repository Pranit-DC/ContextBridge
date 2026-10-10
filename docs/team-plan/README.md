# Three-member implementation plan

Planning baseline: 11 October 2026, `develop` at
`81e37e94cf24c0fa6dae5616affb90d7d87242aa`.

The goal is a finished, tested V1 of ContextBridge: useful memory shared between agents,
with evidence, safe updates, relevant retrieval, a viewer, and reliable operation.
This document assigns the remaining work. It does not claim these features already exist.

## Read your own plan and the common contract

| Member | Main responsibility | Separate plan | First deliverable |
| --- | --- | --- | --- |
| Pranit | Shared engine, storage, API, workers, agent integration | [Pranit](pranit.md) | Contract types and durable interaction ingestion |
| Om | Capture format, extraction, admission, consolidation proposals | [Om](om.md) | Extractor and admission tests using recorded examples |
| Harshal | Hybrid retrieval, inspection viewer, evaluation | [Harshal](harshal.md) | Retrieval against an in-memory repository and viewer against a fake API |

All three read [contracts V1](contracts-v1.md). You do not need to read another member's
implementation plan to begin. The [sample fixtures](fixtures/) contain ordinary test data,
not credentials or instructions for an agent to obey.

**Start all three tracks together.** Om and Harshal use sample data and small fake dependencies
while Pranit builds the real service. A fake is a test substitute with the same inputs and outputs.
It allows independent module development; it cannot prove the real system works.

No plan can guarantee zero merge conflicts or eliminate final integration dependencies.
Exclusive file ownership removes the usual overlapping edits. Real database/provider/agent
integration remains a shared release gate, with Pranit responsible for connecting the modules.

## What is done, and what remains

Already implemented: explicit create, keyword search, project/developer scope, versioned updates,
evidence/history inspection, forgetting, local MCP tools, and Linux/Windows setup and CI.
The existing suite has 83 tests; its last recorded full run passed with 98% coverage.
Pranit and Om reported a successful real Codex-to-Codex test across different networks.
That test covered shared explicit memory, updates, history, and forgetting.

Still required for finished V1:

- Capture/import interactions through supported adapters; capture limitations must be visible.
- Extract useful candidates, keep evidence, reject guesses and filler, and handle uncertainty.
- Resolve corrections and conflicts without silently treating the newest statement as true.
- Add semantic + lexical + structured retrieval, bounded graph expansion, and evidence checks.
- Add durable jobs, retries, consolidation, deletion across derived data, and recovery checks.
- Provide a usable inspection viewer, measured evaluation, installation instructions, and a demo.
- Run real supported-agent tests, including Claude Code, plus same-device and Windows checks.

Keep the local-first, single-configured-developer scope. The current bearer token grants access
to that developer's store; project labels are not separate user permissions. Public SaaS hosting,
multi-user accounts, mobile apps, and autonomous repository editing are outside this V1.
Gemini or another agent can be added through a compatible adapter, but is listed as supported
only after its actual connection and behavior are tested.

## Exclusive file ownership

These are proposed new directories, not existing finished modules.

| Owner | Files they may change |
| --- | --- |
| Pranit | All existing core files in `src/contextbridge/`; existing `mcp_adapter/`; new `contracts/`, `engine/`, `persistence/`, `background/`, `capture_adapters/`; `migrations/`; shared manifests/config/CI; existing root tests and `tests/conftest.py`; new `tests/engine/`, `tests/background/`, `tests/integration/`; existing setup/demo scripts; common docs |
| Om | New `src/contextbridge/formation/`; `tests/formation/`; `scripts/formation/`; `docs/formation/`; `evaluation/formation/`; `docs/team-plan/om.md` |
| Harshal | New `src/contextbridge/retrieval/`, `src/contextbridge/inspection/`; `tests/retrieval/`, `tests/inspection/`; `scripts/retrieval/`; `docs/retrieval/`, `docs/inspection/`; `evaluation/retrieval/`, `evaluation/end_to_end/`; `docs/team-plan/harshal.md` |

Pranit owns shared hotspots: `pyproject.toml`, `uv.lock`, `compose.yaml`, `.env.example`,
`.env.mcp.example`, `Dockerfile`, `.github/`, root `README.md`, `AGENTS.md`, API schemas,
database models, migrations, and common contracts/fixtures. Om/Harshal do not edit those files
in their PRs. They also do not create their own database, queue, or authentication system.
Within an owned directory, each member can add their own `__init__.py` and test helpers.
Do not change the root package initializer or shared test fixtures from another track.

For a shared change, describe the exact dependency, setting, endpoint, or migration needed
in your module's `integration-request.md`. Send the request to Pranit through normal team
discussion. Pranit opens a small shared-file PR. Meanwhile, continue with your fake/provider
interface or another independent task in your plan. Do not merge another member's feature
branch into yours to obtain unfinished code.

## Common interfaces let us work independently

The contracts document fixes field names, inputs, outputs, ownership, and failure behavior.
The JSON fixtures give concrete examples. Use those immediately with Python dictionaries and
local test substitutes. Once Pranit's shared types land, adapt your module boundary to them.
Do not publish competing shared types or change your algorithm just to import a new class.

Before adding an optional library, give Pranit its package name, purpose, and supported platforms.
Keep first PRs runnable with today's installed dependencies. Pranit adds the selected libraries
and lockfile in small PRs; optional UI/model code must not break importing the base API.
Real embedding/LLM integration needs an agreed provider and resources later, even though
unit development needs neither subscriptions nor model credentials.

## Branch and PR routine — all members

First commit or otherwise preserve your own unfinished work. Then run from the repo,
in Bash or PowerShell; replace the example branch name with your task:

```text
git fetch origin
git switch develop
git pull --ff-only origin develop
git switch -c feat/om-extraction-contract
uv sync --frozen --python 3.12
```

Use `feat/pranit-...`, `feat/om-...`, or `feat/harshal-...`. Create a new short-lived branch for
each deliverable. Target **`develop` only**. Never push, merge, or implement directly on `main`.
The team manually releases stable work to `main`.

Before opening a PR:

1. Run your module tests and the [required repository checks](../../AGENTS.md).
   Full integration tests use a dedicated database ending in `_test`, never your real memory DB.
2. Run `git diff --name-only origin/develop...HEAD`; confirm every changed file is owned by you.
3. Update from `origin/develop` and resolve conflicts in your own files. Ask the owner about a
   shared-file conflict; never accept all incoming/ours changes blindly.
4. Show the behavior, test evidence, contract version, and incomplete integration in the PR.
5. Obtain a teammate's review and green required CI. The team merges to `develop`.
6. Start the next task from the updated `develop`; do not keep one huge branch for your whole track.

Use [Windows setup](../windows-setup.md) or [README testing](../../README.md#checks-and-tests)
for database/test environment instructions. Module tests may use fakes, but a full-suite run
with integration tests skipped is not a complete verification result.

## Parallel delivery rounds

Rounds describe outcomes, not a promise that the product fits into a few days. Members can
move ahead within their own track while another round is being integrated.

| Round | Pranit | Om | Harshal | Shared evidence |
| --- | --- | --- | --- | --- |
| 1: interfaces and local behavior | Shared types, ingestion, job records | Extract/admit against fixtures | Rank against fake repository; viewer fake API | Contract examples match; scoped module tests pass |
| 2: real components | Storage adapters, pgvector, worker infrastructure | Real configurable extraction provider; calibration cases | Real embedder, hybrid policy; API viewer | Each real component tested separately, failures included |
| 3: complete flow | Wire write/read paths, capture adapters, deletion fences | Consolidation proposals and quality measurements | Evidence verification, graph expansion, evaluation runner | Real capture → memory → retrieval → inspect/update/forget |
| 4: finish and release review | Recovery, setup, supported-agent/OS tests | Extraction/admission regression fixes | Usability fixes, measured report and demo | All release gates below pass with recorded evidence |

Integrate each small PR as it becomes ready, rather than waiting until everyone's track is complete.
If a dependency is missing, complete the fake-backed part and mark the real integration test
pending. A module is done locally when its contract tests pass; the product is done only after
the integrated gates pass.

## Required release gates

| Gate | What must pass | Main owner |
| --- | --- | --- |
| Memory correctness | Evidence-backed writes; duplicate replay; version conflicts; temporal/conditional facts; unresolved conflicts visible | Pranit + Om |
| Retrieval correctness | Relevant semantic/lexical/identifier queries; scope/time/conditions enforced; compact cards; uncertain results labelled | Harshal + Pranit |
| Failure handling | Provider timeout/malformed output; queue redelivery; worker crash/restart; stale index; unavailable DB; recovery | Pranit, with module owners |
| Forgetting | Remove versions/evidence/edges/embeddings/derived content; pending jobs cannot recreate deleted memory | Pranit |
| User flow | Viewer search, browse, evidence/history, explicit correction, confirmed delete, safe error messages | Harshal |
| Actual agents and OS | Codex and Claude Code share memory; new session sees it; same-machine cross-agent and cross-network tests; Linux + Windows setup | Pranit coordinates; all execute |
| Quality report | Labelled dataset, fixed holdout cases, keyword baseline comparison, latency/provider cost, limitations | Harshal + Om |
| Delivery | Full required CI, migration/recovery evidence, clean install walkthrough, supported-feature list, working demo, team approval | Pranit coordinates; all review |

Hard correctness cases require zero scope leaks, credential echoes, silent conflicting overwrites,
or forgotten-content resurrection. For model quality and latency, measure a baseline, agree
targets before tuning on a separate dataset, and record the decision. Do not invent accuracy
percentages or treat code coverage as proof of model quality.

## A short update each member can share

```text
Member / branch / PR:
Delivered behavior:
Tests run and results:
Contract version: 1
Shared change requested, if any:
Real integration still pending:
Next independent task:
```

Only recorded passing gates belong in the final presentation. The college dates are a reporting
deadline, not evidence that the remaining product is finished.
