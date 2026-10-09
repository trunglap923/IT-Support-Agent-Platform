# UI modernization — Phase 1 foundation

Phase 1 establishes the visual and component foundation used by the remaining
screen-level modernization work. It changes presentation and reusable frontend
contracts while preserving routes, API calls, authentication, and business
behavior.

## Visual direction

The foundation targets a calm, compact operations workspace:

- neutral canvas and white working surfaces;
- one restrained blue accent;
- semantic green, amber, red, and information colors;
- 1 px borders, 8–12 px radii, and low elevation shadows;
- readable 14 px body text and 12–13 px metadata;
- visible keyboard focus and reduced motion support.

## Token system

`frontend/src/styles/00-foundation.css` now owns:

- canvas, surface, selected, hover, raised, and disabled states;
- subtle, standard, strong, and interactive borders;
- strong, standard, muted, subtle, and disabled text;
- accent hover, pressed, soft, border, and focus colors;
- success, warning, danger, and information colors;
- typography, spacing, radius, elevation, control height, and motion scales.

Backward-compatible aliases remain for the existing feature styles. This lets
later phases migrate one feature at a time without changing all markup at once.

## Typography and color cleanup

| Measure | Phase 0 | Phase 1 |
| --- | ---: | ---: |
| Explicit 8–11 px font declarations | 114 | 0 |
| Distinct hexadecimal colors | 131 | 32 |

Feature metadata now resolves to the shared 12 px token or larger. Legacy blue,
gray, green, amber, red, border, and surface values were mapped to semantic
tokens while keeping the existing meaning of each state.

## Shared primitive contract

`frontend/src/components/ProductUI.tsx` now provides:

- `Button` with primary, secondary, danger, and ghost variants;
- `Panel` as the base bounded surface;
- `TextField` and `SelectField` with labels, hints, errors, and accessible
  descriptions;
- `SearchField` with an accessible label;
- `Toolbar` with an explicit toolbar name;
- `Tabs` with selected and disabled states;
- the existing page header, metric, section header, icon button, drawer, badge,
  empty, loading, alert, access denied, and confirmation components.

Existing class-based buttons, forms, panels, tables, and feedback states use the
same tokenized styles. Feature components can therefore move to the React
primitives incrementally in later phases.

## Interaction states

The shared controls now include:

- hover, active, focus, disabled, and invalid states;
- consistent 32, 36, and 40 px control sizes;
- focus rings that remain visible on white and tinted surfaces;
- semantic status indicators with text and a color-independent dot;
- table row hover, stable horizontal scroll gutters, and readable headers;
- modal backdrop blur and consistent drawer elevation;
- a global `prefers-reduced-motion` fallback.

## Responsive corrections

The larger readable type exposed two narrow-screen issues during browser review.
Phase 1 also:

- reserves enough height for the mobile dashboard chart legend;
- makes filter controls use the full mobile width;
- preserves search icon spacing after generic input styles;
- stacks service status content on mobile to prevent badge and text overlap.

## Visual evidence

| View | Phase 1 reference |
| --- | --- |
| Dashboard desktop | [image](assets/ui-modernization/phase-1/dashboard-desktop.png) |
| Dashboard mobile | [image](assets/ui-modernization/phase-1/dashboard-mobile.png) |
| Chat desktop | [image](assets/ui-modernization/phase-1/chat-desktop.png) |
| Chat mobile | [image](assets/ui-modernization/phase-1/chat-mobile.png) |
| Operations mobile | [image](assets/ui-modernization/phase-1/operations-mobile.png) |
| Login desktop | [image](assets/ui-modernization/phase-1/login-desktop.png) |

Compare these with the complete
[Phase 0 baseline](ui-modernization-phase-0.md#baseline-gallery).

## Verification

- ESLint
- TypeScript typecheck
- Vitest component and application tests
- Vite production build
- Playwright responsive layout suite at desktop and mobile widths
- Manual screenshot review for dashboard, chat, operations, documents, memory,
  and login
- Markdown link and secret scans before commit

## Next phase boundary

Phase 2 can now modernize the application shell using the stable foundation:
sidebar grouping and active states, account menu, compact top bar, page canvas,
and mobile navigation. Feature-specific chat and operations layouts remain for
their later phases.
