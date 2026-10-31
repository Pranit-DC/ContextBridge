# ContextBridge workspace design

The workspace is a tool for developers to browse, save and inspect evidence-backed memory.
Keep its existing green identity, system fonts, sidebar shell and explicit project switch.

Use `app/tokens.css` for colour, typography, spacing and motion. The green accent marks actions,
selection and focus. Use neutral text for ordinary metadata. Surfaces use compact, padded panels for distinct tasks. A panel uses a single neutral border
and a raised surface; internal groups use rules or a tinted well, never another bordered card.
Notices contain their own padding and a compact action row. Independently interactive memory
records have one border outside panels, and use separated rows when inside a task panel.
Never place decorative icon tiles above status values or a card inside another card.

Use one page heading and a short description. Status is a compact definition list. Memory text
leads the save form; classification and optional conditions follow evidence. Keep consent,
version checks, confirmation steps and API calls with their existing component owners.

Inputs use a 40px desktop minimum and buttons a 36px minimum; mobile controls are 44px or taller. Keep visible
field labels, instant keyboard focus rings, native checkbox semantics and reduced-motion support.
The centred content container caps at 1120px. Preserve existing loading, empty, error and full
states. Do not add fabricated figures, sample records, provider claims or photographs.

Workspace views use an allowlisted `view` query parameter so refresh and browser history preserve
screen selection. Memory text, credentials and drafts never go in that URL. On phones, the header
shows project context and service status; the destination heading remains in the content. Dialog
headers and close controls stay visible while evidence scrolls. Narrow-phone mode buttons stack
before labels wrap, and secondary action rows wrap between controls.


Dark appearance uses neutral charcoal for the canvas, with lighter graphite task panels and
neutral inset fields. Teal is reserved for actions, selection and focus. Notices use neutral
surfaces with restrained semantic borders/icons; never tint an entire warning panel brown.
Dark dialogs use the raised surface and a hairline edge rather than a drop shadow.


## Soft workspace restyle

This branch keeps all seven layouts and destinations. The shared visual direction is soft and
spacious: off-white canvas, near-white raised panels, quiet neutral sidebar, restrained teal
selection, and neutral charcoal dark mode. Preserve the logo and Segoe UI/system stack.
Page headings are 28px, body text 16px, supporting copy 14px. Panels have 12px corners and 28px
desktop/20px phone padding; controls have 8px corners and 44px field/touch targets. Keep the
1120px content cap and existing responsive columns. Light panels may have a faint tokenized
shadow; dark panels communicate elevation through surface lightness and hairline borders.

Motion is deliberately limited: 120ms hover colors, 180ms dialog fades with at most 4px movement,
and 200ms mobile drawer opacity/transform. No page entrances, stagger, bounce or animated desktop
sidebar dimensions. Expanded sidebar labels may fade for 120ms. Keyboard focus and state updates
remain immediate; reduced motion disables these decorative transitions. Dialog focus restores
to its invoking control and mobile sheets retain keyboard trapping and Escape behavior.
