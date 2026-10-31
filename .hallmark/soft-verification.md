# Soft workspace restyle verification

Branch: `codex/hallmark-soft-workspace`, created from `origin/develop` at `29a2979`.
PR #52 had already merged into that baseline; its branch and PR were not changed.
Common contract V1, API interfaces, database schema and browser storage formats are unchanged.

## Change

All seven Next.js workspace screens keep their navigation, layouts, content and handlers.
Shared tokens provide off-white/light and neutral charcoal/dark surfaces, raised panels,
28px headings, 16px body text, 14px supporting copy, 12px panel corners and 8px controls.
Panels use 28px desktop and 20px mobile padding. The content cap remains 1120px.

Motion is limited to 120ms hover colors/sidebar label fades, 180ms dialog opacity/4px movement,
and 200ms mobile drawer opacity/8px movement. Desktop sidebar dimensions change immediately.
Reduced motion disables the added decorative transitions. Dialog closure keeps the owner mounted
through the exit, then invokes the existing close callback and restores focus to the invoking
control, falling back to the current navigation item if that control no longer exists.

## Validation

- Production build and TypeScript passed; Prettier, diff whitespace, Ruff check and Ruff format passed.
- Dedicated `contextbridge_hallmark_test`: migrations and Alembic drift check passed.
- Full Python suite: **1,775 passed, 4 skipped**, 85% coverage, 20 warnings. The four real worker
  transport probes require a dedicated Redis test broker; Windows Docker remains pending.
- Playwright: **16 passed**, including the existing 13 flows and new reduced-motion, invoking-focus/
  long-evidence-dialog, and rapid mobile-drawer regression cases.
- Before: 28 screenshots covering seven screens, two themes and 1440/375px.
- After: 70 screen-state checks covering all seven screens, both themes and 320/375/1280/1440/1920px;
  no axe violations or document horizontal overflow.
- Another 30 edge-state checks cover migration, locked storage, long project names, service errors
  and long evidence dialogs in both themes at 320/375/1440px; no axe violations or overflow.
- Following finish-review fixes, Connections was recaptured in both themes at 320px. The capture
  configuration button retains one text line, with no clipping, overflow or axe violations.

## Hallmark

Rendered all seven screens: **0 FAIL, 0 REFLEX, 9 WARN, 5 DISMISSED**. Preserved inventory:
4/4 links, 22/22 fields, 24/24 headings, 1/1 figures; 91/92 original inline handlers retained.
The remaining inline handler is explicitly recorded in the CSS stamp: the dialog's direct close
callback is replaced by an adapter preserving that callback after exit and restoring keyboard focus.
The lifecycle and focus regressions verify it.

Warnings are the intentional zero-height sidebar layout spacer on each of seven views, a memory
record's deliberately wrapping accessible name, and the linter's inability to follow the shared
async `run()` wrapper to awaited HTTP requests. The five contrast suspicions concern inherited
paired theme ink; the actual rendered light/dark contrast checks pass. No open Floor or Reflex
finding remains.

Independent finish review returned `fix` with two findings: the capture status button wrapped at
320px, and two hover selectors retained a near-instant rather than disabled reduced-motion fallback.
Both were resolved and confirmed in the narrow-screen captures and passing browser regressions.
The prior version used more compact provider subtitles on phones; the new supporting-text wrapping
is the explicitly chosen spaciousness tradeoff.

## Artifacts and limits

Open `.hallmark/soft/compare.html` in this worktree for the interactive before/after comparison;
choose Light/Dark and Desktop/Phone. Images and JSON reports are in `.hallmark/soft/before/`,
`after/` and `states/`, with the finish confirmation in `confirm.json`. Generated artifacts are
ignored by Git. Hallmark's additional render comparison is `.hallmark/compare.html`.

UI checks use synthetic memory data, a dedicated test store, and simulated vault/Docker/provider
services. They do not establish native credential migration, actual agent-host/provider acceptance,
or Windows Docker readiness. The retained legacy Streamlit interface was not changed.

## Slate-blue accent and sidebar follow-up

Replaced the green accent with muted slate blue for primary actions, selection, focus, logo and
favicon in both themes. The desktop sidebar now gives a restrained 180ms/6px slide-and-fade on
collapse/expand; no layout dimensions are animated and reduced motion disables the effect.
Fresh production build/TypeScript, Prettier, Ruff check/format and all 16 browser regressions
passed, including dark-mode axe checks across seven screens and collapse/reduced-motion/rapid
mobile toggles. The full backend and 100-state results above are from the preceding restyle run;
they were not rerun for this small frontend follow-up.
