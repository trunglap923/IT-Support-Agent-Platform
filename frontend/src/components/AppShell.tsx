import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../features/auth/useAuth";

const navItems = [
  { to: "/", label: "Tổng quan", end: true },
  { to: "/chat", label: "Chat" },
  { to: "/tickets", label: "Ticket" },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function handleLogout() {
    setLogoutError(null);
    setIsLoggingOut(true);
    try {
      await logout();
    } catch {
      setLogoutError("Không thể đăng xuất. Hãy thử lại.");
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <div className="app-frame">
      <header className="topbar">
        <NavLink className="brand" to="/">
          <span className="brand-mark">IT</span>
          <span>
            <strong>Support Agent</strong>
            <small>Workspace demo</small>
          </span>
        </NavLink>
        <nav aria-label="Điều hướng chính">
          {navItems.map((item) => (
            <NavLink
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              end={item.end}
              key={item.to}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
          {user?.role !== "employee" ? <NavLink className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/operations">Vận hành</NavLink> : null}
          {user?.role === "admin" ? <NavLink className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/admin/documents">Tài liệu</NavLink> : null}
        </nav>
        <div className="account-menu">
          <span>{user?.display_name}</span>
          <small>{user?.role} · {user?.department_key}</small>
          <button
            className="ghost-button"
            disabled={isLoggingOut}
            onClick={() => void handleLogout()}
            type="button"
          >
            {isLoggingOut ? "Đang thoát…" : "Đăng xuất"}
          </button>
          {logoutError ? <small className="logout-error" role="alert">{logoutError}</small> : null}
        </div>
      </header>
      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  );
}
