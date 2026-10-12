import { lazy, Suspense, type ComponentType } from "react";
import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { LoadingState } from "./components/ProductUI";
import { RequireAuth } from "./features/auth/RequireAuth";

const ChatPage = lazy(async () => ({ default: (await import("./features/chat/ChatPage")).ChatPage }));
const DashboardPage = lazy(async () => ({ default: (await import("./features/DashboardPage")).DashboardPage }));
const LoginPage = lazy(async () => ({ default: (await import("./features/auth/LoginPage")).LoginPage }));
const DocumentsPage = lazy(async () => ({ default: (await import("./features/documents/DocumentsPage")).DocumentsPage }));
const TicketsPage = lazy(async () => ({ default: (await import("./features/tickets/TicketsPage")).TicketsPage }));
const TicketDetailPage = lazy(async () => ({ default: (await import("./features/tickets/TicketDetailPage")).TicketDetailPage }));
const OperationsPage = lazy(async () => ({ default: (await import("./features/services/OperationsPage")).OperationsPage }));
const MemoryPage = lazy(async () => ({ default: (await import("./features/memory/MemoryPage")).MemoryPage }));
const NotFoundPage = lazy(async () => ({ default: (await import("./features/NotFoundPage")).NotFoundPage }));

function routeElement(Page: ComponentType) {
  return (
    <Suspense fallback={<div className="route-loading"><LoadingState label="Đang tải màn hình…" /></div>}>
      <Page />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: routeElement(LoginPage),
  },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: routeElement(DashboardPage) },
      { path: "chat", element: routeElement(ChatPage) },
      { path: "tickets", element: routeElement(TicketsPage) },
      { path: "tickets/:ticketId", element: routeElement(TicketDetailPage) },
      { path: "operations", element: routeElement(OperationsPage) },
      { path: "admin/documents", element: routeElement(DocumentsPage) },
      { path: "settings/memory", element: routeElement(MemoryPage) },
      { path: "*", element: routeElement(NotFoundPage) },
    ],
  },
  { path: "*", element: routeElement(NotFoundPage) },
]);
