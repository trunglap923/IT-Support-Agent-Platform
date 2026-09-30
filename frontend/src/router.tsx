import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { ChatPage } from "./features/chat/ChatPage";
import { DashboardPage } from "./features/DashboardPage";
import { LoginPage } from "./features/auth/LoginPage";
import { DocumentsPage } from "./features/documents/DocumentsPage";
import { RequireAuth } from "./features/auth/RequireAuth";
import { TicketsPage } from "./features/tickets/TicketsPage";
import { TicketDetailPage } from "./features/tickets/TicketDetailPage";
import { OperationsPage } from "./features/services/OperationsPage";
import { MemoryPage } from "./features/memory/MemoryPage";
import { NotFoundPage } from "./features/NotFoundPage";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "chat", element: <ChatPage /> },
      { path: "tickets", element: <TicketsPage /> },
      { path: "tickets/:ticketId", element: <TicketDetailPage /> },
      { path: "operations", element: <OperationsPage /> },
      { path: "admin/documents", element: <DocumentsPage /> },
      { path: "settings/memory", element: <MemoryPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
