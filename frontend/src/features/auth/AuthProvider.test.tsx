import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";

const currentSession = {
  user: {
    id: "11111111-1111-1111-1111-111111111111",
    email: "employee.engineering@example.com",
    display_name: "Engineering Employee",
    role: "employee",
    department_id: "22222222-2222-2222-2222-222222222222",
    department_key: "engineering",
  },
  csrf_token: "csrf-demo-token",
};

function SessionProbe() {
  const { user, isLoading, logout } = useAuth();
  if (isLoading) return <p>Đang tải</p>;
  if (!user) return <p>Chưa đăng nhập</p>;
  return (
    <button onClick={() => void logout()} type="button">
      Đăng xuất {user.display_name}
    </button>
  );
}

describe("AuthProvider", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("bootstraps the session and clears it after a CSRF-protected logout", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(currentSession), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <SessionProbe />
        </AuthProvider>
      </QueryClientProvider>,
    );

    const logoutButton = await screen.findByRole("button", {
      name: "Đăng xuất Engineering Employee",
    });
    fireEvent.click(logoutButton);

    expect(await screen.findByText("Chưa đăng nhập")).toBeInTheDocument();
    await waitFor(() =>
      expect(fetchMock).toHaveBeenLastCalledWith(
        "/api/v1/auth/logout",
        expect.objectContaining({
          method: "POST",
          credentials: "same-origin",
          headers: expect.objectContaining({ "X-CSRF-Token": "csrf-demo-token" }),
        }),
      ),
    );
  });
});
