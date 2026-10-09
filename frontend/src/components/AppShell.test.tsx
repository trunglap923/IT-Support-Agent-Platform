// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthContextValue } from "../features/auth/authContext";
import { useAuth } from "../features/auth/useAuth";
import { AppShell } from "./AppShell";

vi.mock("../features/auth/useAuth", () => ({ useAuth: vi.fn() }));

const mockedUseAuth = vi.mocked(useAuth);
const logout = vi.fn<() => Promise<void>>();

function authValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    user: {
      id: "11111111-1111-1111-1111-111111111111",
      email: "admin@example.com",
      display_name: "Demo Administrator",
      role: "admin",
      department_id: "22222222-2222-2222-2222-222222222222",
      department_key: "operations",
    },
    csrfToken: "csrf-token",
    isLoading: false,
    login: vi.fn(),
    logout,
    ...overrides,
  };
}

function renderShell(path = "/chat") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="*" element={<p>Nội dung trang</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    logout.mockReset().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue(authValue());
  });

  it("groups role-aware navigation and marks the current page", () => {
    renderShell();

    expect(screen.getByText("Workspace", { selector: ".nav-group-label" })).toBeInTheDocument();
    expect(screen.getByText("Cá nhân", { selector: ".nav-group-label" })).toBeInTheDocument();
    expect(screen.getByText("Vận hành", { selector: ".nav-group-label" })).toBeInTheDocument();
    expect(screen.getByText("Quản trị", { selector: ".nav-group-label" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Trợ lý AI" })).toHaveClass("active");
    expect(screen.getByLabelText("Vị trí hiện tại")).toHaveTextContent("WorkspaceTrợ lý AI");
  });

  it("hides privileged navigation from employees", () => {
    mockedUseAuth.mockReturnValue(authValue({
      user: {
        id: "33333333-3333-3333-3333-333333333333",
        email: "employee@example.com",
        display_name: "Engineering Employee",
        role: "employee",
        department_id: "22222222-2222-2222-2222-222222222222",
        department_key: "engineering",
      },
    }));
    renderShell("/");

    expect(screen.queryByRole("link", { name: "Hàng đợi IT" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Kho tri thức" })).not.toBeInTheDocument();
    expect(screen.getByText("Nhân viên · engineering")).toBeInTheDocument();
  });

  it("opens the notification popover and closes it with Escape", () => {
    renderShell();
    const trigger = screen.getByRole("button", { name: "Thông báo" });

    fireEvent.click(trigger);
    expect(screen.getByText("Không có thông báo mới")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByText("Không có thông báo mới")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("moves logout into the account menu", async () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: /Demo Administrator/ }));
    fireEvent.click(screen.getByRole("button", { name: "Đăng xuất" }));

    await waitFor(() => expect(logout).toHaveBeenCalledOnce());
  });

  it("opens and closes the mobile navigation drawer", () => {
    renderShell();
    const navigation = screen.getByLabelText("Điều hướng ứng dụng");

    fireEvent.click(screen.getByRole("button", { name: "Mở điều hướng" }));
    expect(navigation).toHaveClass("open");
    fireEvent.keyDown(document, { key: "Escape" });

    expect(navigation).not.toHaveClass("open");
    expect(screen.getByRole("button", { name: "Mở điều hướng" })).toHaveFocus();
  });
});
