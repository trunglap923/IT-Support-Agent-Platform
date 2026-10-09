# UI modernization — Phase 0 baseline

Phase 0 records the existing interface and separates the stylesheet into
reviewable layers. It intentionally does not change API contracts, routes,
business rules, component markup, or the visual direction.

## Baseline environment

- Browser: Playwright Chromium
- Desktop viewport: 1440 × 960
- Wide dashboard reference: 1680 × 960
- Mobile viewport: 390 × 844
- Data source: deterministic route fixtures from
  `frontend/e2e/responsive-layout.pw.ts`
- Capture date: 2026-10-09

The responsive layout suite passed before and after the stylesheet split.

## Baseline gallery

| View | Desktop | Mobile |
| --- | --- | --- |
| Dashboard | [desktop](assets/ui-baseline/phase-0/dashboard-desktop.png) | [mobile](assets/ui-baseline/phase-0/dashboard-mobile.png) |
| Chat | [desktop](assets/ui-baseline/phase-0/chat-desktop.png) | [mobile](assets/ui-baseline/phase-0/chat-mobile.png) |
| Streaming response | [desktop](assets/ui-baseline/phase-0/chat-streaming-desktop.png) | [mobile](assets/ui-baseline/phase-0/chat-streaming-mobile.png) |
| Tickets | [desktop](assets/ui-baseline/phase-0/tickets-desktop.png) | [mobile](assets/ui-baseline/phase-0/tickets-mobile.png) |
| Ticket detail | [desktop](assets/ui-baseline/phase-0/ticket-detail-desktop.png) | [mobile](assets/ui-baseline/phase-0/ticket-detail-mobile.png) |
| Operations | [desktop](assets/ui-baseline/phase-0/operations-desktop.png) | [mobile](assets/ui-baseline/phase-0/operations-mobile.png) |
| Documents | [desktop](assets/ui-baseline/phase-0/documents-desktop.png) | [mobile](assets/ui-baseline/phase-0/documents-mobile.png) |
| Memory | [desktop](assets/ui-baseline/phase-0/memory-desktop.png) | [mobile](assets/ui-baseline/phase-0/memory-mobile.png) |
| Login | [desktop](assets/ui-baseline/phase-0/login-desktop.png) | [mobile](assets/ui-baseline/phase-0/login-mobile.png) |
| Mobile navigation | — | [open drawer](assets/ui-baseline/phase-0/navigation-mobile.png) |

The [1680 px dashboard reference](assets/ui-baseline/phase-0/dashboard-reference-1680.png)
is retained for large-screen density comparisons.

## Audit findings

### 1. The cascade contains an old base and later refinements

The original 918-line stylesheet first defines feature layouts and then changes
the same layouts in later sections. Examples include:

- `body` changes from 14 px to 13 px;
- `.app-frame` changes its top row from 56 px to 44 px;
- `.chat-layout` changes from two columns to three columns;
- `.dashboard-grid` is defined in three different stages;
- `.panel`, `.run-error`, and `.quick-actions` have context-dependent overrides.

Removing any of these rules without consolidating the final computed values can
cause large layout changes. Phase 0 therefore preserves their order in numbered
stylesheet layers.

### 2. Typography is too small for operational content

There are 72 declarations using an 8 px, 9 px, or 10 px font size. They appear
in timestamps, source metadata, service status, memory records, Agent progress,
and action labels. Many of these values should move to a 12–13 px metadata scale
in Phase 1 and later feature phases.

### 3. Color usage has escaped the token system

The stylesheet contains 131 distinct hexadecimal color values. Similar blues,
grays, greens, and amber values are repeated as one-off literals. Phase 1 should
map them to a compact set of surface, text, border, accent, and semantic tokens.

### 4. Shared patterns have parallel implementations

- Dashboard uses both `.metrics-strip`/`.metric` and
  `.metric-grid`/`.metric-card`.
- Feature-specific drawers coexist with the shared `Drawer` component.
- Search controls, compact buttons, status cards, and section headers are styled
  separately across features.
- Legacy dashboard and list rules remain below newer shared component rules.

The React components in `frontend/src/components/ProductUI.tsx` should become
the single implementation point as each screen is modernized.

### 5. Responsive rules are fragmented

Responsive behavior is split across 640 px, 900 px, 1100 px, and 1101 px media
queries in separate sections. The current behavior works, but ownership is hard
to follow. Each modernized feature should keep its responsive rules with its
desktop rules and follow the same desktop, tablet, and mobile breakpoints.

### 6. The product structure can be retained

The existing routes, role-aware navigation, three-column chat workspace,
drawers, tables, loading states, empty states, and Lucide icon dependency are a
sound base. The modernization can focus on hierarchy, typography, components,
and interaction states without replacing the application architecture.

## Stylesheet transition map

| File | Current purpose | Modernization action |
| --- | --- | --- |
| `00-foundation.css` | Existing tokens and global rules | Replace with the Phase 1 visual foundation |
| `10-shell.css` | Sidebar, top bar, and page canvas | Modernize in Phase 2 |
| `20-primitives.css` | Legacy shared UI rules | Consolidate into shared components in Phase 1 |
| `30-feature-baseline.css` | Original feature styles | Remove sections as each feature is migrated |
| `40-workspace-refinements.css` | Later visual overrides | Eliminate through consolidation |
| `50-shared-components.css` | Newer shared components | Keep and expand in Phase 1 |
| `60-chat-progress.css` | Chat activity and breakpoints | Modernize with the chat workspace in Phase 3 |

## Phase 0 acceptance evidence

- Twenty baseline screenshots are stored under
  `docs/assets/ui-baseline/phase-0/`.
- CSS remains loaded through the existing `frontend/src/styles.css` entry point.
- Ordered stylesheet layers preserve the previous cascade.
- The responsive Playwright suite passes all ten scenarios after the split.
- No API, route, data contract, or component behavior changed.

## Next phase boundary

Phase 1 can now replace the visual foundation and shared primitives without
editing a 900-line monolithic file. It should begin with tokens and typography,
then migrate buttons, form controls, panels, status badges, tables, loading,
empty, alert, drawer, and toolbar patterns.
