# Production-style workspace refinement

The user requested a second full UI refinement after reviewing Settings with legacy provider keys.
This revision continues the user-authorized isolated `codex/hallmark-workspace` branch from `441089f`.
It changes the frontend and its browser regressions; no memory engine, schema, provider adapter,
credential store or API contract was changed.

## Result

- All seven destinations share compact typography, padded task panels, consistent controls and
  restrained green selection/action states. The main content caps at 1120px.
- Migration is a bounded notice with its original explanation and consent, plus a compact action
  row. It no longer inherits a zero-padding surface or a stretched full-width grid button.
- Settings providers use aligned panels. Optional preferences and connection checks remain
  disclosures. Secondary action rows wrap between controls on narrow phones.
- The phone header separates project context and Docker status; the destination is already
  present in the content heading. Long project names truncate without overlapping service warnings.
- The evidence dialog has a pinned header and a close control that stays visible while scrolling.
- An allowlisted `view` query parameter preserves navigation across refresh, Back and Forward.
  Browser tab titles follow the screen. Authentication still removes the private launch fragment.
  No memory content, credential, project switch or draft is persisted in the view URL.
- Existing actions, source/evidence text, consent, version fences and deletion confirmations remain.
  The visible MCP action label became “Connection instructions” to fit a 320px phone; its original
  “Generate connection instructions” accessible name and handler remain intact.

## Validation

- Production build, frontend typecheck, Prettier and diff whitespace checks passed.
- Required Ruff lint and formatting checks passed.
- Alembic upgrade and drift check passed on `contextbridge_hallmark_test`.
- Full Python suite: 1,775 passed, 4 skipped, 20 warnings, 85% coverage. The four skips require
  a dedicated Redis test broker for real worker transport probes.
- Playwright: all 10 tests passed on `contextbridge_hallmark_ui_test`. The original seven tests
  remain intact; three new tests cover navigation refresh/history and drafts, explicit migration
  consent at desktop/phone widths, and long project names alongside service warnings at 320/375px.
- Screenshot inspection: 22 desktop/phone screen-state checks passed with no axe violations or
  horizontal overflow: all seven destinations plus legacy migration, locked keyring, service error
  and memory details. The dialog close control was asserted visible after scrolling.
- Final Hallmark render across all seven directly addressable screens: 0 FAIL, 0 REFLEX, 9 WARN.
  It writes 35 screenshots and checks responsive widths from 320 to 1920. Final field-edge
  contrast is at least 3.28:1 against the sidebar and 3.52:1 against the main page.
- Kept inventory: 4/4 links, 1/1 rendered Overview fields, 5/5 Overview headings. 89 source handler
  bodies remain identical; two `setView` wrappers intentionally became `navigate` wrappers to
  retain their actions while adding history. Both replacements are recorded in the CSS stamp
  and covered by browser tests. No action was deleted. The inventory is not a count of every
  form control; the existing browser lifecycle tests cover those forms separately.
- Fresh-context Hallmark reviewer identified one mobile header collision. It was fixed, recaptured
  and supplemented by the 320/375px long-project/service-warning regression. The reviewer found
  the migration notice, provider alignment and evidence hierarchy substantially improved.

## Reviewed warnings

Seven F18 warnings are the same intentional zero-height sidebar layout spacer, one per route,
not missing imagery. Gate 49 is the deliberately wrapping accessible label of a whole memory
record. Gate 70 cannot trace the shared async `run()` wrapper to awaited HTTP requests; the
lifecycle and settings regressions verify that behavior. No Floor or Reflex finding is left open.

## Preview

Open `compare.html` beside this file for the updated side-by-side comparison. Generated screenshots
and inventories are ignored by Git. `production/review/` contains the full screen-state captures.
No placeholder images or fabricated product metrics were added.

## Run the build

Stop the existing UI launcher with Ctrl+C first, then run:

```bash
PYTHONPATH=/tmp/contextbridge-hallmark/src \
/home/pranitchiman/Projects/ContextBridge/.venv/bin/contextbridge \
start --root /home/pranitchiman/Projects/ContextBridge --port 8502
```

This uses the existing local installation's settings and memory store with the new UI assets.
Restarting the launcher reloads the generated asset/CSP set. The automated UI checks instead use
isolated test stores and simulated OS/provider services. They do not establish native credential
migration, live provider quality, actual agent-host acceptance or Windows Docker readiness.

## Project switching and appearance follow-up

The sidebar now offers the configured project and up to 20 recently used project identifiers.
Opening another project requires entering its name once; confirmed selections and the last active
project are saved in this browser. This is a recent-project list, not a server project directory:
the current API does not expose that directory. Selecting an option stages the switch, with an
explicit draft-loss warning, confirmation and cancellation. Confirming on mobile closes the drawer.
No credentials, memory contents or drafts are added to browser storage.

The header offers System, Light and Dark appearance. System tracks OS changes; explicit choices
survive reload. A CSP-hashed startup script applies the choice before hydration. Both controls
continue working for the current session when browser storage is unavailable. Dark colors use
shared tokens for panels, fields, focus, alerts, text and navigation.

Follow-up verification: production build and TypeScript, Prettier, Ruff and whitespace checks;
13 Playwright regressions including remembered projects, cancellation, refresh, mobile drawer
closure, unavailable storage, appearance persistence, OS changes, dark-mode axe checks on all
seven screens and 320/375px overflow checks. Backend, migrations and the earlier 22-state visual
sweep were not rerun for this frontend-only follow-up; their results above refer to the prior run.
