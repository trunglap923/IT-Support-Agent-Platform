import { useCallback, useEffect, useRef, useState, type ComponentType } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Bell,
  BookOpen,
  Bot,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Gauge,
  LogOut,
  Menu,
  MonitorCog,
  Tickets,
  X,
  type LucideProps,
} from "lucide-react";

import { useAuth } from "../features/auth/useAuth";
import { useMediaQuery } from "../hooks/useMediaQuery";

interface NavigationItem {
  to: string;
  label: string;
  icon: ComponentType<LucideProps>;
  end?: boolean;
}

interface NavigationGroupProps {
  label: string;
  items: NavigationItem[];
}

interface PageMetadata {
  section: string;
  title: string;
}

const workspaceNav: NavigationItem[] = [
  { to: "/", label: "Tổng quan", icon: Gauge, end: true },
  { to: "/chat", label: "Trợ lý AI", icon: Bot },
  { to: "/tickets", label: "Ticket của tôi", icon: Tickets },
];

const personalNav: NavigationItem[] = [
  { to: "/settings/memory", label: "Thiết bị & memory", icon: MonitorCog },
];

const operationsNav: NavigationItem[] = [
  { to: "/operations", label: "Hàng đợi IT", icon: ClipboardList },
];

const administrationNav: NavigationItem[] = [
  { to: "/admin/documents", label: "Kho tri thức", icon: BookOpen },
];

const pageMetadata: Record<string, PageMetadata> = {
  "/": { section: "Workspace", title: "Tổng quan" },
  "/chat": { section: "Workspace", title: "Trợ lý AI" },
  "/tickets": { section: "Cá nhân", title: "Ticket của tôi" },
  "/operations": { section: "Vận hành", title: "Hàng đợi IT" },
  "/admin/documents": { section: "Quản trị", title: "Kho tri thức" },
  "/settings/memory": { section: "Cá nhân", title: "Thiết bị & memory" },
};

const roleLabels: Record<string, string> = {
  admin: "Quản trị viên",
  employee: "Nhân viên",
  it: "IT Support",
};

function NavigationGroup({ label, items }: NavigationGroupProps) {
  return (
    <section className="nav-group">
      <p className="nav-group-label">{label}</p>
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            data-nav-link
            end={item.end}
            key={item.to}
            to={item.to}
          >
            <Icon className="nav-icon" aria-hidden="true" size={18} strokeWidth={1.8} />
            <span>{item.label}</span>
          </NavLink>
        );
      })}
    </section>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const compactNavigation = useMediaQuery("(max-width: 900px)");
  const navigationRef = useRef<HTMLElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const previousPathname = useRef(location.pathname);
  const notificationMenuRef = useRef<HTMLDivElement>(null);
  const notificationButtonRef = useRef<HTMLButtonElement>(null);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const accountButtonRef = useRef<HTMLButtonElement>(null);
  const currentPage = location.pathname.startsWith("/tickets/")
    ? { section: "Cá nhân", title: "Chi tiết ticket" }
    : pageMetadata[location.pathname] ?? { section: "Workspace", title: "Không gian làm việc" };
  const userInitial = user?.display_name?.slice(0, 1).toUpperCase() ?? "U";
  const roleLabel = roleLabels[user?.role ?? ""] ?? user?.role ?? "Người dùng";

  const closeNavigation = useCallback((restoreFocus = true) => {
    setNavigationOpen(false);
    if (restoreFocus) menuButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!navigationOpen) return;
    const previousOverflow = document.body.style.overflow;
    if (compactNavigation) document.body.style.overflow = "hidden";
    navigationRef.current?.querySelector<HTMLElement>("[data-nav-link]")?.focus();
    const handleNavigationKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeNavigation();
        return;
      }
      if (event.key !== "Tab" || !compactNavigation || !navigationRef.current) return;
      const focusable = [...navigationRef.current.querySelectorAll<HTMLElement>(
        "a[href], button:not(:disabled), [tabindex]:not([tabindex='-1'])",
      )].filter((element) => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && (document.activeElement === first || !navigationRef.current.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleNavigationKeyboard);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleNavigationKeyboard);
    };
  }, [closeNavigation, compactNavigation, navigationOpen]);

  useEffect(() => {
    document.title = `${currentPage.title} · IT Support Agent`;
    if (previousPathname.current === location.pathname) return;
    previousPathname.current = location.pathname;
    setNavigationOpen(false);
    requestAnimationFrame(() => mainRef.current?.focus());
  }, [currentPage.title, location.pathname]);

  useEffect(() => {
    if (!notificationOpen && !accountMenuOpen) return;

    const closeOnOutsideInteraction = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!notificationMenuRef.current?.contains(target)) setNotificationOpen(false);
      if (!accountMenuRef.current?.contains(target)) setAccountMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (accountMenuOpen) accountButtonRef.current?.focus();
      if (notificationOpen) notificationButtonRef.current?.focus();
      setNotificationOpen(false);
      setAccountMenuOpen(false);
    };

    document.addEventListener("pointerdown", closeOnOutsideInteraction);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideInteraction);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [accountMenuOpen, notificationOpen]);

  async function handleLogout() {
    setLogoutError(null);
    setIsLoggingOut(true);
    try {
      await logout();
      setAccountMenuOpen(false);
    } catch {
      setLogoutError("Không thể đăng xuất. Hãy thử lại.");
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <div className="app-frame">
      <aside
        aria-label="Điều hướng ứng dụng"
        aria-hidden={compactNavigation && !navigationOpen ? true : undefined}
        aria-modal={compactNavigation && navigationOpen ? true : undefined}
        className={navigationOpen ? "app-sidebar open" : "app-sidebar"}
        inert={compactNavigation && !navigationOpen ? true : undefined}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest("a")) closeNavigation(false);
        }}
        ref={navigationRef}
        role={compactNavigation && navigationOpen ? "dialog" : undefined}
      >
        <div className="sidebar-brand-row">
          <NavLink className="brand" to="/">
            <span className="brand-mark">IT</span>
            <span className="brand-copy">
              <strong>Support Agent</strong>
              <small>Engineering workspace</small>
            </span>
          </NavLink>
          <button
            aria-label="Đóng điều hướng"
            className="sidebar-close-button"
            onClick={() => closeNavigation()}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>

        <nav aria-label="Điều hướng chính" className="sidebar-nav">
          <NavigationGroup items={workspaceNav} label="Workspace" />
          <NavigationGroup items={personalNav} label="Cá nhân" />
          {user?.role !== "employee" ? <NavigationGroup items={operationsNav} label="Vận hành" /> : null}
          {user?.role === "admin" ? <NavigationGroup items={administrationNav} label="Quản trị" /> : null}
        </nav>

        <div aria-label="Tài khoản hiện tại" className="sidebar-account">
          <span className="user-avatar" aria-hidden="true">{userInitial}</span>
          <span className="account-copy">
            <strong>{user?.display_name}</strong>
            <small>{roleLabel} · {user?.department_key}</small>
          </span>
        </div>
      </aside>

      {navigationOpen ? (
        <button
          aria-label="Đóng điều hướng"
          className="sidebar-backdrop"
          onClick={() => closeNavigation()}
          type="button"
        />
      ) : null}

      <header className="topbar">
        <div className="topbar-leading">
          <button
            aria-expanded={navigationOpen}
            aria-label="Mở điều hướng"
            className="menu-button shell-icon-button"
            onClick={() => setNavigationOpen((current) => !current)}
            ref={menuButtonRef}
            type="button"
          >
            <Menu aria-hidden="true" size={18} />
          </button>
          <div aria-label="Vị trí hiện tại" className="topbar-breadcrumb">
            <span>{currentPage.section}</span>
            <ChevronRight aria-hidden="true" size={14} />
            <strong>{currentPage.title}</strong>
          </div>
        </div>

        <div className="topbar-actions">
          <span className="environment-indicator"><i /> Demo environment</span>

          <div className="topbar-menu" ref={notificationMenuRef}>
            <button
              aria-controls="notification-popover"
              aria-expanded={notificationOpen}
              aria-label="Thông báo"
              className="shell-icon-button"
              onClick={() => {
                setNotificationOpen((current) => !current);
                setAccountMenuOpen(false);
              }}
              ref={notificationButtonRef}
              type="button"
            >
              <Bell aria-hidden="true" size={18} />
            </button>
            {notificationOpen ? (
              <section className="topbar-popover notification-popover" id="notification-popover">
                <header>
                  <strong>Thông báo</strong>
                  <small>0 chưa đọc</small>
                </header>
                <div className="notification-empty">
                  <Bell aria-hidden="true" size={18} />
                  <span>
                    <strong>Không có thông báo mới</strong>
                    <small>Các cập nhật quan trọng sẽ xuất hiện tại đây.</small>
                  </span>
                </div>
              </section>
            ) : null}
          </div>

          <div className="topbar-menu" ref={accountMenuRef}>
            <button
              aria-controls="account-popover"
              aria-expanded={accountMenuOpen}
              aria-label={`Mở menu tài khoản của ${user?.display_name ?? "người dùng"}`}
              className="account-menu-button"
              onClick={() => {
                setAccountMenuOpen((current) => !current);
                setNotificationOpen(false);
              }}
              ref={accountButtonRef}
              type="button"
            >
              <span className="topbar-avatar" aria-hidden="true">{userInitial}</span>
              <span className="topbar-account-copy">
                <strong>{user?.display_name}</strong>
                <small>{roleLabel}</small>
              </span>
              <ChevronDown className="topbar-chevron" aria-hidden="true" size={14} />
            </button>
            {accountMenuOpen ? (
              <section className="topbar-popover account-popover" id="account-popover">
                <div className="account-popover-profile">
                  <span className="user-avatar" aria-hidden="true">{userInitial}</span>
                  <span>
                    <strong>{user?.display_name}</strong>
                    <small>{user?.email}</small>
                  </span>
                </div>
                <dl>
                  <div><dt>Vai trò</dt><dd>{roleLabel}</dd></div>
                  <div><dt>Phòng ban</dt><dd>{user?.department_key}</dd></div>
                </dl>
                <button
                  className="account-menu-action"
                  disabled={isLoggingOut}
                  onClick={() => void handleLogout()}
                  type="button"
                >
                  <LogOut aria-hidden="true" size={16} />
                  {isLoggingOut ? "Đang đăng xuất…" : "Đăng xuất"}
                </button>
                {logoutError ? <small className="logout-error" role="alert">{logoutError}</small> : null}
              </section>
            ) : null}
          </div>
        </div>
      </header>

      <main aria-label="Nội dung chính" className="page-shell" ref={mainRef} tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
