# Official Blocks.so sidebar-02

Fetched from https://blocks.so/r/sidebar-02.json on 31 October 2026, with
primitives from https://github.com/ephraimduncan/blocks at commit
`3f759d5171c2391253ec4c772e9e5b3db2bc7c7f`.

`sidebar-02.registry.json` retains the exact downloaded block, including all six
original files. `provenance.json` records original SHA-256 hashes and local paths.
The MIT license is retained here and included in distributed frontend notices.

The live component is `components/sidebar-02/app-sidebar.tsx`, using the actual
upstream SidebarProvider/SidebarInset, responsive sheet, navigation and icon collapse.
It is not a visual recreation. Application adaptations:

- Replace Acme/demo notifications/teams and retail routes with ContextBridge's
  actual navigation, project-control slot and About/privacy action.
- Add route callbacks and current-page labels instead of placeholder links.
  Close the real mobile drawer after navigation; retain text on mobile when the
  desktop sidebar was collapsed.
- Connect the upstream provider/inset to the existing workspace and preserve all
  memory/state/credential handlers. Use one main landmark and a mobile trigger.
- Match the existing light/teal theme. Upstream button hover uses sidebar accent
  because this application's existing `muted` token is a text colour.
- Shorten the upstream header animation; keep the existing reduced-motion styling.

Demo-only notifications/team components are retained as upstream source references;
we do not display their fake product features.
