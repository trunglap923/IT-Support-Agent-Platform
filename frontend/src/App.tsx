import { RouterProvider } from "react-router-dom";

import { AppErrorBoundary } from "./components/AppErrorBoundary";
import { router } from "./router";

export function App() {
  return (
    <AppErrorBoundary>
      <RouterProvider router={router} />
    </AppErrorBoundary>
  );
}
