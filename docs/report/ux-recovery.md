# Workspace UX repair

Branch: `codex/workspace-ux-recovery`. This work pauses demo preparation and repairs the
current browser workspace. It does not claim an exhaustive absence of bugs or verified live-agent capture.

## Findings and changes

| Finding | Change |
| --- | --- |
| Action banners appeared above the user's scroll position | Dismissible feedback stays in the viewport; memory dialogs show feedback inside the dialog |
| Checked Free-plan box could differ from the saved setting used by checks | Visible saved/unsaved state; provider checks block unsaved edits and explain why |
| Save button had unexplained disabled states | Nearby reasons cover locked vault, key migration, changed settings, busy operations, and invalid values |
| Missing Cloudflare account ID was discovered only after submission | Account/key requirements and validation are shown before saving |
| Browsing and processing projects used inconsistent controls | Both use remembered project choices; capture reports and blocks a processing-project mismatch |
| Settings mixed service operations and advanced tuning with providers | Separate Providers, Services, and Advanced sections; preserve drafts across sections |
| Docker availability looked like application readiness | Header/Overview report observed service states; do not claim provider or API readiness from configuration alone |
| Exited migration container looked like an application failure | Expose safe exit code and label successful one-time setup as Completed; retain unknown/failure distinctions |
| Service failures could leave old state visible | Refresh service state after both successful and failed apply/stop attempts |
| Connection instructions required assembling JSON by hand | Generate and copy a complete VS Code configuration using actual paths and selected project |
| Routine Activity was dominated by maintenance tools | Keep capture activity first and put maintenance behind a separate disclosure |
| Users had to manually load routine lists | Activity and initial unfiltered memory browsing load on arrival; manual retry remains available |
| Navigation could leave users midway down another screen | Reset scroll and focus the new page heading; preserve browser history and workspace drafts |
| README mixed everyday startup, API contracts, historical reports, and testing | Short README, docs index, plain-language user guide, and separate developer reference; mark legacy launchers clearly |

Project choices are remembered by the browser and include the saved processing project. This is
not a new server-wide project directory. No database schema, memory API, storage format, provider
billing policy, evidence requirement, deletion confirmation, or agent trust boundary was changed.
The local service-status response adds the container exit code for accurate status descriptions.

## Verification

Final results: **25 Chromium tests passed**; **1,780 backend tests passed with no skips**,
85% coverage and 20 existing Alembic deprecation warnings. Production build, TypeScript,
Prettier, Ruff lint/format, migrations, and Alembic schema drift checks passed. Tests use two dedicated databases:
`contextbridge_ux_test` and `contextbridge_ux_browser_test`, plus isolated Redis DB 15.
Provider checks use synthetic fixtures; no real keys, live provider calls, or user workspaces are used.

- Browser regressions include explicit CRUD/evidence/version/deletion, drafts/history,
  project persistence, theme/reduced-motion, dialog focus, rapid drawer toggles,
  save blockers, saved-only provider checks, capture mismatch, and automatic browsing.
- Rendered axe/overflow coverage: all seven screens at 320, 375, and 1440 pixels in both themes;
  all three Settings sections at 320, 375, 1280, and 1920 pixels in both themes.
- Screenshots are captured by Playwright under `frontend/test-results/`. Selected examples are
  retained in `docs/report/screenshots/ux-recovery/`.
- Production build includes TypeScript checking. Repository Ruff checks and PostgreSQL migrations/
  schema drift checks are required separately.

Live Groq/Cloudflare quality and actual Codex/Copilot host behavior are separate acceptance checks.
No new claim of live demo success is made.

## Selected screens

- [Providers, desktop/light](screenshots/ux-recovery/ux-settings-light-1440.png).
- [Providers, phone/dark](screenshots/ux-recovery/ux-settings-dark-375.png).
- [Connections, desktop/dark](screenshots/ux-recovery/ux-connections-dark-1440.png).
- [Overview, desktop/light](screenshots/ux-recovery/ux-overview-light-1440.png).
