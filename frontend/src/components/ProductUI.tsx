import { useEffect, useId, useRef, type ComponentType, type ReactNode } from "react";
import { Inbox, X, type LucideProps } from "lucide-react";

import { formatStatus } from "../utils/format";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-header-actions">{actions}</div> : null}
    </header>
  );
}

export type SemanticTone = "blue" | "green" | "amber" | "red" | "neutral";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  icon: ComponentType<LucideProps>;
  tone?: SemanticTone;
  detail?: ReactNode;
}

export function MetricCard({ label, value, icon: Icon, tone = "blue", detail }: MetricCardProps) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <span className="metric-card-icon" aria-hidden="true"><Icon size={20} strokeWidth={1.9} /></span>
      <span className="metric-card-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        {detail ? <small>{detail}</small> : null}
      </span>
    </article>
  );
}

interface SectionHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function SectionHeader({ title, description, actions }: SectionHeaderProps) {
  return (
    <header className="panel-header">
      <div><h2>{title}</h2>{description ? <p>{description}</p> : null}</div>
      {actions ? <div className="panel-actions">{actions}</div> : null}
    </header>
  );
}

interface IconButtonProps {
  label: string;
  icon: ComponentType<LucideProps>;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
  className?: string;
}

export function IconButton({ label, icon: Icon, className = "", ...props }: IconButtonProps) {
  return (
    <button aria-label={label} className={`icon-button ${className}`.trim()} {...props}>
      <Icon aria-hidden="true" size={17} />
    </button>
  );
}

interface DrawerProps {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}

export function Drawer({ open, title, description, onClose, children, className = "" }: DrawerProps) {
  const drawerRef = useRef<HTMLElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const drawer = drawerRef.current;
    const previousFocus = document.activeElement as HTMLElement | null;
    drawer?.querySelector<HTMLElement>("button, input, textarea, select, a[href]")?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;
  return (
    <>
      <button aria-label={`Đóng nền ${title}`} className="drawer-backdrop" onClick={onClose} type="button" />
      <aside aria-labelledby={titleId} className={`product-drawer ${className}`.trim()} ref={drawerRef}>
        <header className="drawer-header">
          <div><h2 id={titleId}>{title}</h2>{description ? <p>{description}</p> : null}</div>
          <IconButton icon={X} label={`Đóng ${title}`} onClick={onClose} />
        </header>
        {children}
      </aside>
    </>
  );
}

const positiveStates = new Set(["healthy", "published", "ready", "resolved", "executed", "active"]);
const warningStates = new Set(["degraded", "pending", "processing", "waiting_approval", "in_progress", "draft"]);
const dangerStates = new Set(["down", "failed", "expired", "rejected", "revoked", "high", "critical"]);

interface StatusBadgeProps {
  value: string;
  label?: string;
}

export function StatusBadge({ value, label }: StatusBadgeProps) {
  const normalized = value.toLowerCase();
  const tone = positiveStates.has(normalized)
    ? "positive"
    : warningStates.has(normalized)
      ? "warning"
      : dangerStates.has(normalized)
        ? "danger"
        : "neutral";
  return <span className={`status-badge ${tone}`}>{label ?? formatStatus(value)}</span>;
}

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state-mark" aria-hidden="true"><Inbox size={18} /></span>
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Đang tải dữ liệu…" }: { label?: string }) {
  return (
    <div className="loading-state" role="status">
      <span className="loading-spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function AccessDenied({ message }: { message: string }) {
  return (
    <div className="access-denied">
      <span aria-hidden="true">403</span>
      <strong role="alert">{message}</strong>
    </div>
  );
}

export function AlertBanner({ tone, children }: { tone: "success" | "error" | "info"; children: ReactNode }) {
  return <div className={`alert-banner ${tone}`} role={tone === "error" ? "alert" : "status"}>{children}</div>;
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  tone?: "default" | "danger";
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  tone = "default",
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    } else if (!open && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [open]);

  return (
    <dialog
      aria-describedby={descriptionId}
      aria-labelledby={titleId}
      className="confirm-dialog"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onCancel();
      }}
      ref={dialogRef}
    >
      <h2 id={titleId}>{title}</h2>
      <p id={descriptionId}>{description}</p>
      <div className="confirm-dialog-actions">
        <button autoFocus className="secondary-button" disabled={busy} onClick={onCancel} type="button">
          Hủy
        </button>
        <button
          className={tone === "danger" ? "danger-button" : "primary-button"}
          disabled={busy}
          onClick={onConfirm}
          type="button"
        >
          {busy ? "Đang xử lý…" : confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
