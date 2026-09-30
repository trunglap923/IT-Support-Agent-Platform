import { useEffect, useId, useRef, type ReactNode } from "react";

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
  return <span className={`status-badge ${tone}`}>{label ?? value.replaceAll("_", " ")}</span>;
}

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state-mark" aria-hidden="true">·</span>
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
