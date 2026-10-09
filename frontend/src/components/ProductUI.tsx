import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type ComponentType,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { Inbox, Search, X, type LucideProps } from "lucide-react";

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

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ComponentType<LucideProps>;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon: Icon,
  className = "",
  children,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button className={`product-button ${variant} size-${size} ${className}`.trim()} type={type} {...props}>
      {Icon ? <Icon aria-hidden="true" size={16} strokeWidth={1.9} /> : null}
      {children}
    </button>
  );
}

interface PanelProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

export function Panel({ className = "", children, ...props }: PanelProps) {
  return <section className={`product-panel ${className}`.trim()} {...props}>{children}</section>;
}

interface FieldFrameProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

function FieldFrame({ id, label, hint, error, children }: FieldFrameProps) {
  return (
    <div className={error ? "product-field has-error" : "product-field"}>
      <label className="product-field-label" htmlFor={id}>{label}</label>
      {children}
      {error ? <span className="product-field-error" id={`${id}-error`}>{error}</span> : null}
      {!error && hint ? <span className="product-field-hint" id={`${id}-hint`}>{hint}</span> : null}
    </div>
  );
}

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label: string;
  hint?: string;
  error?: string;
}

export function TextField({ label, hint, error, id, className = "", ...props }: TextFieldProps) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const descriptionId = error ? `${controlId}-error` : hint ? `${controlId}-hint` : undefined;
  return (
    <FieldFrame error={error} hint={hint} id={controlId} label={label}>
      <input
        aria-describedby={descriptionId}
        aria-invalid={error ? true : undefined}
        className={`product-field-control ${className}`.trim()}
        id={controlId}
        {...props}
      />
    </FieldFrame>
  );
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function SelectField({ label, hint, error, id, className = "", children, ...props }: SelectFieldProps) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const descriptionId = error ? `${controlId}-error` : hint ? `${controlId}-hint` : undefined;
  return (
    <FieldFrame error={error} hint={hint} id={controlId} label={label}>
      <select
        aria-describedby={descriptionId}
        aria-invalid={error ? true : undefined}
        className={`product-field-control ${className}`.trim()}
        id={controlId}
        {...props}
      >
        {children}
      </select>
    </FieldFrame>
  );
}

interface SearchFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
}

export function SearchField({ label, className = "", ...props }: SearchFieldProps) {
  return (
    <label className={`product-search ${className}`.trim()}>
      <Search aria-hidden="true" size={16} />
      <span className="sr-only">{label}</span>
      <input type="search" {...props} />
    </label>
  );
}

interface ToolbarProps extends HTMLAttributes<HTMLDivElement> {
  label: string;
}

export function Toolbar({ label, className = "", children, ...props }: ToolbarProps) {
  return <div aria-label={label} className={`product-toolbar ${className}`.trim()} role="toolbar" {...props}>{children}</div>;
}

export interface TabItem {
  value: string;
  label: string;
  disabled?: boolean;
}

interface TabsProps {
  label: string;
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
}

export function Tabs({ label, items, value, onChange }: TabsProps) {
  return (
    <div aria-label={label} className="product-tabs" role="tablist">
      {items.map((item) => (
        <button
          aria-selected={item.value === value}
          className="product-tab"
          disabled={item.disabled}
          key={item.value}
          onClick={() => onChange(item.value)}
          role="tab"
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
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

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  label: string;
  icon: ComponentType<LucideProps>;
}

export function IconButton({ label, icon: Icon, className = "", type = "button", ...props }: IconButtonProps) {
  return (
    <button aria-label={label} className={`icon-button ${className}`.trim()} type={type} {...props}>
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
        <Button autoFocus disabled={busy} onClick={onCancel} variant="secondary">
          Hủy
        </Button>
        <Button
          disabled={busy}
          onClick={onConfirm}
          variant={tone === "danger" ? "danger" : "primary"}
        >
          {busy ? "Đang xử lý…" : confirmLabel}
        </Button>
      </div>
    </dialog>
  );
}
