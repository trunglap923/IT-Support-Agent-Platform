import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { ChatPage } from "./features/chat/ChatPage";
import { DashboardPage } from "./features/DashboardPage";
import { LoginPage } from "./features/auth/LoginPage";
import { RequireAuth } from "./features/auth/RequireAuth";
import { TicketsPage } from "./features/tickets/TicketsPage";
import { OperationsPage } from "./features/services/OperationsPage";

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
      { path: "operations", element: <OperationsPage /> },
    ],
  },
]);
