# Frontend stylesheet layers

`frontend/src/styles.css` is the only stylesheet imported by the application. It
loads these files in numeric order so the cascade remains equivalent to the
pre-modernization stylesheet.

| Layer | Responsibility |
| --- | --- |
| `00-foundation.css` | Canonical color, typography, spacing, shape, elevation, focus, and motion tokens |
| `10-shell.css` | Desktop shell, sidebar, top bar, page canvas |
| `20-primitives.css` | Canonical panels, buttons, fields, toolbars, tabs, tables, and feedback states |
| `30-feature-baseline.css` | Original feature rules for dashboard, chat, tickets, documents, memory, and login |
| `40-workspace-refinements.css` | Later compact workspace overrides and responsive rules |
| `50-shared-components.css` | Styles used by the newer shared React components |
| `60-chat-progress.css` | Chat interaction breakpoints and Agent activity timeline |

## Cascade contract

- Keep the import order stable until the remaining feature baseline and
  refinement rules are consolidated in later modernization phases.
- Add new design tokens to `00-foundation.css`.
- Prefer extending components in `ProductUI.tsx`. Primitive styles belong in
  `20-primitives.css`; composed operational components belong in
  `50-shared-components.css`.
- Do not add another catch-all refinement layer. Move a rule into its owning
  component or feature when it is modernized.
- Keep narrow-screen overrides next to the feature once that feature no longer
  depends on the legacy cascade.

The initial findings are recorded in
[`docs/ui-modernization-phase-0.md`](../../../docs/ui-modernization-phase-0.md).
The foundation and primitive contract introduced in Phase 1 is documented in
[`docs/ui-modernization-phase-1.md`](../../../docs/ui-modernization-phase-1.md).
