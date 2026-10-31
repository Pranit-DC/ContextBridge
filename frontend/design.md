# ContextBridge workspace design

The workspace is a tool for developers to browse, save and inspect evidence-backed memory.
Keep its existing green identity, system fonts, sidebar shell and explicit project switch.

Use `app/tokens.css` for colour, typography, spacing and motion. The green accent marks actions,
selection and focus. Use neutral text for ordinary metadata. Surfaces are quiet and predominantly
unboxed; a rule separates form sections. Independently interactive memory records have one border.
Never place decorative icon tiles above status values or a card inside another card.

Use one page heading and a short description. Status is a compact definition list. Memory text
leads the save form; classification and optional conditions follow evidence. Keep consent,
version checks, confirmation steps and API calls with their existing component owners.

Inputs and buttons share a 40px desktop minimum; mobile controls are 44px or taller. Keep visible
field labels, instant keyboard focus rings, native checkbox semantics and reduced-motion support.
The centred content container caps at 1200px. Preserve existing loading, empty, error and full
states. Do not add fabricated figures, sample records, provider claims or photographs.
