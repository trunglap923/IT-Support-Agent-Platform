import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../features/auth/useAuth";

const primaryNav = [
  { to: "/", label: "Tổng quan", glyph: "⌂", end: true },
  { to: "/chat", label: "Trợ lý AI", glyph: "✦" },
  { to: "/tickets", label: "Ticket của tôi", glyph: "▣" },
];

const contextNav = [
  { to: "/settings/memory", label: "Thiết bị & memory", glyph: "▤" },
];

const pageNames: Record<string, string> = {
  "/": "Tổng quan",
  "/chat": "Trợ lý AI",
  "/tickets": "Ticket của tôi",
  "/operations": "Hàng đợi IT",
  "/admin/documents": "Kho tri thức",
  "/settings/memory": "Thiết bị & memory",
};

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const currentPageName = location.pathname.startsWith("/tickets/")
    ? "Chi tiết ticket"
    : pageNames[location.pathname] ?? "Workspace";

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
      <aside
        className={navigationOpen ? "app-sidebar open" : "app-sidebar"}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a")) setNavigationOpen(false);
        }}
      >
        <NavLink className="brand" to="/">
          <span className="brand-mark">IT</span>
          <span>
            <strong>Support Agent</strong>
            <small>Engineering workspace</small>
          </span>
        </NavLink>

        <nav aria-label="Điều hướng chính" className="sidebar-nav">
          {primaryNav.map((item) => (
            <NavLink
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              end={item.end}
              key={item.to}
              to={item.to}
            >
              <span className="nav-glyph" aria-hidden="true">{item.glyph}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}

          {contextNav.map((item) => (
            <NavLink className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} key={item.to} to={item.to}>
              <span className="nav-glyph" aria-hidden="true">{item.glyph}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}

          {user?.role !== "employee" ? (
            <>
              <NavLink className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/operations">
                <span className="nav-glyph" aria-hidden="true">▥</span>
                <span>Hàng đợi IT</span>
              </NavLink>
            </>
          ) : null}
          {user?.role === "admin" ? (
            <NavLink className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/admin/documents">
              <span className="nav-glyph" aria-hidden="true">◇</span>
              <span>Kho tri thức</span>
            </NavLink>
          ) : null}
        </nav>

        <div className="sidebar-account">
          <div className="sidebar-identity">
            <span className="user-avatar" aria-hidden="true">{user?.display_name?.slice(0, 1).toUpperCase() ?? "U"}</span>
            <span className="account-copy">
              <strong>{user?.display_name}</strong>
              <small>{user?.role} · {user?.department_key}</small>
            </span>
          </div>
          <button
            className="ghost-button"
            disabled={isLoggingOut}
            onClick={() => void handleLogout()}
            type="button"
          >
            <span aria-hidden="true">↪</span> {isLoggingOut ? "Đang đăng xuất…" : "Đăng xuất"}
          </button>
          {logoutError ? <small className="logout-error" role="alert">{logoutError}</small> : null}
        </div>
      </aside>

      {navigationOpen ? <button aria-label="Đóng điều hướng" className="sidebar-backdrop" onClick={() => setNavigationOpen(false)} type="button" /> : null}

      <header className="topbar">
        <button
          aria-expanded={navigationOpen}
          aria-label="Mở điều hướng"
          className="menu-button"
          onClick={() => setNavigationOpen((current) => !current)}
          type="button"
        >
          <span />
          <span />
          <span />
        </button>
        <div className="topbar-title">
          <small>IT Support</small>
          <strong>{currentPageName}</strong>
        </div>
        <div className="topbar-context">
          <span className="environment-indicator"><i /> Demo environment</span>
          <span className="topbar-divider" />
          <span className="notification-mark" aria-label="Thông báo">♧<i /></span>
          <span className="topbar-divider" />
          <span className="topbar-avatar" aria-hidden="true">{user?.display_name?.slice(0, 1).toUpperCase() ?? "U"}</span>
          <strong className="topbar-user-name">{user?.display_name}</strong>
        </div>
      </header>

      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  );
}
