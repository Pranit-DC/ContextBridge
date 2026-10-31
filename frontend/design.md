# ContextBridge workspace design

The workspace is a tool for developers to browse, save and inspect evidence-backed memory.
Keep its existing green identity, system fonts, sidebar shell and explicit project switch.

Use `app/tokens.css` for colour, typography, spacing and motion. The green accent marks actions,
selection and focus. Use neutral text for ordinary metadata. Surfaces use compact, padded panels for distinct tasks. A panel uses a single neutral border
and the page surface; internal groups use rules or a tinted well, never another bordered card.
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
