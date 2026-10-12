# UI modernization — Phase 3 assistant workspace

Phase 3 modernizes the AI assistant workspace while preserving the existing
conversation, message, citation, approval, run, and feedback API contracts.

## What changed

### Conversation navigation

- Added a clear heading, conversation count, grouped history, and an explicit
  empty search result.
- Preserved the existing date grouping, time labels, previews, pagination, and
  selected conversation behavior.
- On small screens, the conversation list opens as a workspace drawer with a
  backdrop, close button, Escape handling, and focus restoration.

### Chat and answer presentation

- Reworked the assistant header and user/assistant messages with consistent
  identity, timestamps, spacing, and readable answer width.
- Styled numbered instructions as a compact sequence and kept Markdown, code,
  and lists readable.
- Presented citations in a labeled source panel with document count, page
  details, excerpts, and external-link indicators.
- Grouped copy, ticket creation, and feedback actions into clear action rows.
- Improved the empty state with contextual starter actions.

### Agent activity and composer

- Restyled the activity card and its timeline states using the actual backend
  progress events. The UI does not invent steps.
- Added a focused composer surface, character count, disabled state, send action,
  and Ctrl/Command + Enter shortcut.
- Kept the separate conversation, message, and context scroll areas on desktop.

### Context rail and responsive layout

- Preserved reference sources, related devices, recent tickets, pending actions,
  and contextual quick actions in a compact right rail.
- Collapsed the context rail into a native disclosure on tablet and mobile, with
  the initial state following the viewport width.
- Replaced the old mobile conversation strip with an on-demand overlay drawer.
- Consolidated chat-specific styles into `frontend/src/styles/60-chat-workspace.css`.

## Browser review

Screenshots use deterministic Playwright fixtures at 1680 × 940 desktop and
390 × 844 mobile viewports.

| State | Evidence |
| --- | --- |
| Desktop conversation, answer, and context | [screenshot](assets/ui-modernization/phase-3/chat-desktop.png) |
| Mobile conversation view | [screenshot](assets/ui-modernization/phase-3/chat-mobile.png) |
| Mobile conversation drawer | [screenshot](assets/ui-modernization/phase-3/conversations-mobile.png) |
| Expanded mobile context | [screenshot](assets/ui-modernization/phase-3/context-mobile.png) |
| Agent activity timeline | [screenshot](assets/ui-modernization/phase-3/agent-progress-desktop.png) |

## Verification

- ESLint passed.
- TypeScript typecheck passed.
- Vitest passed: 20 files and 59 tests.
- Production build passed. Vite reports the main JavaScript chunk at about 991
  KB, above its 500 KB advisory threshold.
- Playwright Chromium passed: 11 responsive and chat workspace scenarios.
- The covered pages had no horizontal overflow or browser console errors.

## Next phase boundary

Phase 4 can modernize ticket and operations workflows. The assistant workspace
and application shell should remain stable while those pages are migrated.
