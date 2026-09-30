# Frontend Design Guidelines

## Product direction

This repository contains an internal IT Support operations product. The UI must feel calm, compact, professional, and information-dense, in the spirit of mature productivity software such as Linear, GitHub, Jira, or Zendesk. It is not a marketing site.

Preserve existing API contracts, routing behavior, authentication, business rules, and data structures during visual work. Only change business logic to fix a verified bug.

## Application shell

- Use a persistent left sidebar on desktop, a compact top bar, and a neutral main canvas.
- Keep sidebar navigation grouped, with a clearly visible active state and the account area at the bottom.
- Use 24px desktop page padding and a readable content width where appropriate.
- Collapse navigation behind an accessible menu on narrow screens.

## Visual system

- Use the tokens in frontend/src/styles.css; do not introduce one-off colors or spacing without a strong reason.
- Prefer neutral gray surfaces, white panels, subtle 1px borders, 6-8px radii, and minimal shadow.
- Use one restrained blue accent plus semantic success, warning, danger, and neutral colors.
- Typography: page title 22-26px semibold, section title 15-17px semibold, body 14px, metadata 12-13px.
- Spacing scale: 4, 8, 12, 16, 24, and 32px.
- Avoid gradients, decorative hero sections, oversized typography, excessive rounding, large empty areas, and card grids where a list or table communicates better.

## Reusable UI

Prefer shared components from frontend/src/components/ProductUI.tsx, including page headers, status badges, empty states, loading states, and alerts. Extend these patterns instead of duplicating markup and styles.

- Tables should have compact rows, clear headers, row hover, useful metadata, and graceful narrow-screen behavior.
- Forms should have visible labels, consistent controls, validation feedback, disabled states, and focused keyboard states.
- Every important view should account for default, hover, active/selected, loading, empty, error, and disabled states.
- Use semantic badges for ticket, document, service, run, and approval states.
- Do not add an icon library unless the product genuinely needs it. If an icon library already exists, use it rather than drawing SVG icons manually.

## IT support UX

Optimize every operational view to answer: what needs attention, how urgent it is, who owns it, its current state, what changed, and the next available action.

Prefer:

- search + filters + compact table for ticket and document collections;
- conversation/work on the left and ticket/context details on the right;
- concise metrics and a needs-attention queue on dashboards;
- explicit approval, access, memory-confirmation, and SLA language.

## Verification

After meaningful frontend work:

1. Run lint, typecheck, unit tests, and the production build.
2. Run the application and inspect the rendered UI in a real browser.
3. Capture and review Playwright screenshots at desktop and mobile widths when available.
4. Check alignment, spacing, typography, overflow, density, focus/hover states, borders, and console errors.
5. Fix obvious visual problems before declaring the slice complete.

