import type { ReactNode } from "react";

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
