import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthProvider";
import { RequireAuth } from "./RequireAuth";

describe("RequireAuth", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("redirects an unauthenticated visitor to login", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/private"]}>
            <Routes>
              <Route path="/login" element={<p>Trang đăng nhập</p>} />
              <Route
                path="/private"
                element={
                  <RequireAuth>
                    <p>Dữ liệu riêng</p>
                  </RequireAuth>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Trang đăng nhập")).toBeInTheDocument();
    expect(screen.queryByText("Dữ liệu riêng")).not.toBeInTheDocument();
  });
});
