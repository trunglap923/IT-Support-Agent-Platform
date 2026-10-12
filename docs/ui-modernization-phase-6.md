# UI modernization — Phase 5 and Phase 6 acceptance

The final modernization slice completes responsive behavior, accessibility,
performance cleanup, and browser verification without changing authentication,
routing semantics, or business workflows.

## Responsive behavior

- Large desktop retains the three-region assistant workspace.
- Laptop keeps the three regions with a narrower conversation list and context rail.
- Tablet moves application navigation and assistant context into modal drawers.
- Mobile uses one chat column, an independently scrolling message list, and a
  persistent composer within the viewport.
- Ticket, document, and navigation drawers trap keyboard focus on compact
  screens, close with Escape, and return focus to their trigger.

## Accessibility checks

- Interactive elements use a shared visible focus ring.
- Icon-only controls have accessible names.
- Drawer state is exposed through `aria-expanded`, `aria-controls`, dialog roles,
  and modal state at compact breakpoints.
- Loading, error, and success feedback uses status or alert live regions.
- Semantic foreground/background pairs meet WCAG AA contrast for normal text.
- `prefers-reduced-motion` reduces animations and transitions globally.

## Final engineering cleanup

- Ticket summary cards now use scoped database aggregates instead of counting
  only the current 20-row page.
- Route-level lazy loading reduced the production entry bundle from about
  998 kB to 370 kB uncompressed. The largest lazy route remains below Vite's
  500 kB warning threshold.
- Responsive Playwright fixtures cover desktop, tablet, and mobile overflow,
  drawer focus behavior, reduced motion, and icon-button naming.

## Reviewed screenshots

| View | Desktop | Mobile |
| --- | --- | --- |
| Dashboard | [desktop](assets/ui-modernization/phase-6/dashboard-desktop.png) | [mobile](assets/ui-modernization/phase-6/dashboard-mobile.png) |
| Assistant | [desktop](assets/ui-modernization/phase-6/chat-desktop.png) | [mobile](assets/ui-modernization/phase-6/chat-mobile.png) |
| Streaming response | [desktop](assets/ui-modernization/phase-6/chat-streaming-desktop.png) | [mobile](assets/ui-modernization/phase-6/chat-streaming-mobile.png) |
| Tickets | [desktop](assets/ui-modernization/phase-6/tickets-desktop.png) | [mobile](assets/ui-modernization/phase-6/tickets-mobile.png) |
| Ticket detail | [desktop](assets/ui-modernization/phase-6/ticket-detail-desktop.png) | [mobile](assets/ui-modernization/phase-6/ticket-detail-mobile.png) |
| Operations | [desktop](assets/ui-modernization/phase-6/operations-desktop.png) | [mobile](assets/ui-modernization/phase-6/operations-mobile.png) |
| Documents | [desktop](assets/ui-modernization/phase-6/documents-desktop.png) | [mobile](assets/ui-modernization/phase-6/documents-mobile.png) |
| Memory | [desktop](assets/ui-modernization/phase-6/memory-desktop.png) | [mobile](assets/ui-modernization/phase-6/memory-mobile.png) |
| Login | [desktop](assets/ui-modernization/phase-6/login-desktop.png) | [mobile](assets/ui-modernization/phase-6/login-mobile.png) |

The tablet assistant context drawer is captured in
[chat-context-tablet.png](assets/ui-modernization/phase-6/chat-context-tablet.png).

## Verification

The acceptance run uses the repository commands below:

```bash
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
make test-e2e
```

Backend formatting, linting, typing, and the PostgreSQL-backed ticket API suite
also cover the new aggregate endpoints.
