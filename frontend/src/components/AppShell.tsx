import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Tổng quan", end: true },
  { to: "/chat", label: "Chat" },
];

export function AppShell() {
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
        </nav>
        <NavLink className="ghost-button" to="/login">
          Đăng nhập demo
        </NavLink>
      </header>
      <main className="page-shell">
        <Outlet />
      </main>
    </div>
  );
}
