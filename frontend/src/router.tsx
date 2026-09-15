import { createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { ChatPlaceholderPage } from "./features/ChatPlaceholderPage";
import { DashboardPage } from "./features/DashboardPage";
import { LoginPage } from "./features/auth/LoginPage";
import { RequireAuth } from "./features/auth/RequireAuth";

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
      { path: "chat", element: <ChatPlaceholderPage /> },
    ],
  },
]);
