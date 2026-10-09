# UI modernization — Phase 2 application shell

Phase 2 modernizes the persistent application shell while preserving existing
routes, role checks, authentication behavior, and feature data contracts.

## What changed

### Sidebar navigation

- Increased the desktop sidebar to 240 px so labels and account metadata remain
  readable without making the workspace feel wide.
- Grouped links into Workspace, Personal, Operations, and Administration.
- Kept Operations and Administration links behind the existing role checks.
- Added a restrained selected state with a blue edge, tinted surface, and icon
  color instead of relying on a large filled navigation block.
- Retained the current account summary at the bottom of the sidebar.

### Top bar and account actions

- Added a compact section/page breadcrumb for better location awareness.
- Replaced the decorative notification indicator with an interactive, honest
  empty state. The UI no longer implies unread notifications without data.
- Moved logout into an account menu that also exposes the current role,
  department, and email address.
- Added outside-click and Escape handling to both top-bar menus, including focus
  restoration for keyboard users.

### Responsive shell

- Standardized the shell around a 56 px top bar and a shared CSS token used by
  chat and feature drawers.
- Applied 24 px page padding on desktop, 16 px on tablet, and 12 px on mobile.
- Kept the chat workspace full width with its compact 8 px edge spacing.
- Rebuilt the mobile navigation as a fixed drawer with a backdrop, internal
  close action, scroll locking, Escape support, and focus restoration.

## Browser review

| State | Evidence |
| --- | --- |
| Desktop dashboard shell | [screenshot](assets/ui-modernization/phase-2/dashboard-shell-desktop.png) |
| Notification popover | [screenshot](assets/ui-modernization/phase-2/notification-popover-desktop.png) |
| Account menu | [screenshot](assets/ui-modernization/phase-2/account-popover-desktop.png) |
| Mobile navigation drawer | [screenshot](assets/ui-modernization/phase-2/navigation-mobile.png) |
| Desktop chat shell | [screenshot](assets/ui-modernization/phase-2/chat-shell-desktop.png) |
| Mobile chat shell | [screenshot](assets/ui-modernization/phase-2/chat-shell-mobile.png) |

The screenshots were captured with deterministic Playwright fixtures at 1440 ×
960 and 390 × 844. The review covered alignment, typography, overflow, drawer
stacking, selected navigation, top-bar menus, and responsive spacing.

## Verification

- ESLint: passed.
- TypeScript typecheck: passed.
- Vitest: 20 files and 59 tests passed.
- Production build: passed. Vite still reports the existing large bundle warning
  for the main JavaScript chunk.
- Playwright Chromium responsive suite: all 10 scenarios passed.
- No horizontal overflow or browser console errors were found in the covered
  routes.

## Next phase boundary

Phase 3 can now modernize the assistant workspace itself: conversation list,
message rhythm, structured answers, activity state, composer, and context rail.
The application shell should remain stable while those feature-specific styles
move out of the legacy refinement layer.
