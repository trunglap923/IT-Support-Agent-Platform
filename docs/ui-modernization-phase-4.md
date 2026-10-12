# UI modernization — Phase 4: tickets and IT operations

Phase 4 modernizes ticket tracking, ticket details, and the IT operations queue.
It preserves existing routes, access checks, ticket transitions, approval rules,
and API contracts.

## What changed

- Clarified the ticket status summary with selected states exposed to assistive
  technology and a result count that follows the current filters.
- Refined the ticket table for faster scanning of ticket codes, titles, issue
  descriptions, priority, status, and update time.
- Made ticket titles in the IT queue open their existing detail route.
- Presented the ticket description and resolution note as a readable activity
  timeline, with status and requester context kept in a compact detail panel.
- Tightened service status cards and made queue metrics readable on narrow
  screens. The queue table keeps its horizontal scroll affordance on mobile.
- Kept the create drawer closed on an initial mobile visit, then provided a
  backdrop, keyboard focus containment, Escape handling, and focus restoration
  when the user opens it.
- Added consistent hover and keyboard focus treatments using the shared token
  system.

## Browser review

Screenshots use deterministic Playwright fixtures at 1440 × 960 desktop and
390 × 844 mobile viewports.

| State | Evidence |
| --- | --- |
| Ticket list | [desktop](assets/ui-modernization/phase-4/tickets-desktop.png), [mobile](assets/ui-modernization/phase-4/tickets-mobile.png) |
| Mobile create drawer | [screenshot](assets/ui-modernization/phase-4/ticket-drawer-mobile.png) |
| Ticket detail and activity | [desktop](assets/ui-modernization/phase-4/ticket-detail-desktop.png), [mobile](assets/ui-modernization/phase-4/ticket-detail-mobile.png) |
| IT service status and ticket queue | [desktop](assets/ui-modernization/phase-4/operations-desktop.png), [mobile](assets/ui-modernization/phase-4/operations-mobile.png) |

## Verification

- ESLint passed.
- TypeScript typecheck passed.
- Vitest passed: 20 files and 61 tests.
- Production build passed. Vite still reports the main JavaScript chunk at
  about 994 KB, above its 500 KB advisory threshold.
- Playwright passed: 3 responsive ticket/operations scenarios and 6 ticket
  workflow scenarios, including create/approve/reject, resolve/reopen,
  permissions, and service state changes.
- Desktop and mobile screenshots were reviewed; no horizontal page overflow or
  blocking layout issue remained in the covered views.

## Next phase boundary

Phase 5 can finish the remaining operational pages and visual consistency pass.
