import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Activity, CheckCircle2, Clock3, ListFilter, Plus, Search, TicketCheck, X } from "lucide-react";

import { cancelRun, getRunSnapshot } from "../../api/run-events";
import { getOrCreateClientRequest, type ClientRequestIdentity } from "../../api/idempotency";
import {
  createTicketDraft,
  decideApproval,
  getMyTicketSummary,
  listMyTicketsPage,
  listPendingApprovalsPage,
  type Approval,
  type Ticket,
  type TicketDraftArguments,
  type TicketSummary,
} from "../../api/tickets";
import { useAuth } from "../auth/useAuth";
import { EmptyState, LoadingState, PageHeader, StatusBadge } from "../../components/ProductUI";
import { ApprovalCard } from "./ApprovalCard";
import { formatIssueType, formatRelativeTime } from "../../utils/format";

const initialDraft: TicketDraftArguments = {
  title: "",
  description: "",
  issue_type: "other",
  severity: "normal",
  device_id: null,
};

export function TicketsPage() {
  const { csrfToken } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [summary, setSummary] = useState<TicketSummary>({
    total: 0, open: 0, in_progress: 0, resolved: 0, high_unresolved: 0,
  });
  const [draft, setDraft] = useState<TicketDraftArguments>(initialDraft);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [issueTypeFilter, setIssueTypeFilter] = useState("all");
  const [ticketCursor, setTicketCursor] = useState<string | null>(null);
  const [approvalCursor, setApprovalCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState<"tickets" | "approvals" | null>(null);
  const [draftOpen, setDraftOpen] = useState(() =>
    typeof window.matchMedia !== "function" || window.matchMedia("(min-width: 901px)").matches,
  );
  const titleInput = useRef<HTMLInputElement>(null);
  const draftTrigger = useRef<HTMLButtonElement>(null);
  const draftDialog = useRef<HTMLElement>(null);
  const pendingDraftRequest = useRef<ClientRequestIdentity | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      listMyTicketsPage(null, controller.signal, {
        ...(statusFilter !== "all" ? { ticket_status: statusFilter } : {}),
        ...(severityFilter !== "all" ? { severity: severityFilter } : {}),
        ...(issueTypeFilter !== "all" ? { issue_type: issueTypeFilter } : {}),
      }),
      listPendingApprovalsPage(null, controller.signal),
      getMyTicketSummary(controller.signal),
    ])
      .then(([ticketPage, approvalPage, ticketSummary]) => {
        setTickets(ticketPage.items);
        setTicketCursor(ticketPage.next_cursor);
        setApprovals(approvalPage.items);
        setApprovalCursor(approvalPage.next_cursor);
        setSummary(ticketSummary);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải ticket.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [issueTypeFilter, severityFilter, statusFilter]);

  useEffect(() => {
    if (!draftOpen) return;
    const handleDrawerKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDraftOpen(false);
        requestAnimationFrame(() => draftTrigger.current?.focus());
        return;
      }
      if (
        event.key !== "Tab"
        || typeof window.matchMedia !== "function"
        || !window.matchMedia("(max-width: 900px)").matches
        || !draftDialog.current
      ) return;
      const focusable = [...draftDialog.current.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex='-1'])",
      )].filter((element) => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && (document.activeElement === first || !draftDialog.current.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleDrawerKeyboard);
    return () => document.removeEventListener("keydown", handleDrawerKeyboard);
  }, [draftOpen]);

  async function loadMore(kind: "tickets" | "approvals") {
    const cursor = kind === "tickets" ? ticketCursor : approvalCursor;
    if (!cursor || loadingMore) return;
    setLoadingMore(kind);
    setError(null);
    try {
      if (kind === "tickets") {
        const page = await listMyTicketsPage(cursor, undefined, {
          ...(statusFilter !== "all" ? { ticket_status: statusFilter } : {}),
          ...(severityFilter !== "all" ? { severity: severityFilter } : {}),
          ...(issueTypeFilter !== "all" ? { issue_type: issueTypeFilter } : {}),
        });
        setTickets((current) => [...current, ...page.items]);
        setTicketCursor(page.next_cursor);
      } else {
        const page = await listPendingApprovalsPage(cursor);
        setApprovals((current) => [...current, ...page.items]);
        setApprovalCursor(page.next_cursor);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải thêm dữ liệu.");
    } finally {
      setLoadingMore(null);
    }
  }

  async function submitDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken || submitting) return;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const request = getOrCreateClientRequest(
        pendingDraftRequest.current,
        JSON.stringify(draft),
      );
      pendingDraftRequest.current = request;
      const created = await createTicketDraft(draft, csrfToken, request.id);
      pendingDraftRequest.current = null;
      setApprovals((current) => [created.approval, ...current]);
      setDraft(initialDraft);
      setNotice("Bản nháp đã được tạo. Hãy kiểm tra và xác nhận bên dưới.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tạo bản nháp.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDecision(approval: Approval, decision: "approve" | "reject") {
    if (!csrfToken) return;
    setError(null);
    try {
      await decideApproval(approval, decision, csrfToken);
      setApprovals((current) => current.filter((item) => item.id !== approval.id));
      setNotice(
        decision === "approve"
          ? "Đã xác nhận. Worker đang tạo ticket an toàn."
          : "Đã từ chối bản nháp.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể xử lý phê duyệt.");
    }
  }

  async function handleEdit(approval: Approval) {
    if (!csrfToken) return;
    setError(null);
    setNotice(null);
    try {
      const run = await getRunSnapshot(approval.run_id);
      await cancelRun(run.id, run.version, csrfToken, "draft_replaced");
      setApprovals((current) => current.filter((item) => item.id !== approval.id));
      setDraft({ ...approval.canonical_args });
      setNotice("Đã hủy bản nháp cũ. Hãy chỉnh sửa rồi tạo bản nháp mới.");
      titleInput.current?.focus();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể sửa bản nháp.");
    }
  }

  const filteredTickets = useMemo(() => tickets.filter((ticket) => {
    const matchesQuery = `${ticket.display_key} ${ticket.title} ${ticket.description}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery
      && (statusFilter === "all" || ticket.status === statusFilter)
      && (severityFilter === "all" || ticket.severity === severityFilter);
  }), [query, severityFilter, statusFilter, tickets]);

  function openDraftPanel() {
    setDraftOpen(true);
    requestAnimationFrame(() => titleInput.current?.focus());
  }

  function closeDraftPanel() {
    setDraftOpen(false);
    requestAnimationFrame(() => draftTrigger.current?.focus());
  }

  if (loading) return <LoadingState label="Đang tải ticket…" />;

  return (
    <div className={draftOpen ? "tickets-page draft-visible" : "tickets-page"}>
      <PageHeader
        eyebrow="IT SUPPORT"
        title="Ticket của tôi"
        description="Theo dõi yêu cầu và xác nhận rõ nội dung trước khi tạo ticket."
        actions={<button className="primary-button" onClick={openDraftPanel} ref={draftTrigger} type="button"><Plus aria-hidden="true" size={16} /> Tạo ticket</button>}
      />

      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="ticket-summary" aria-label="Tổng quan ticket">
        <button aria-pressed={statusFilter === "all"} className={statusFilter === "all" ? "active" : ""} onClick={() => setStatusFilter("all")} type="button"><span className="summary-icon"><ListFilter /></span><span>Tất cả</span><strong>{summary.total}</strong></button>
        <button aria-pressed={statusFilter === "open"} className={statusFilter === "open" ? "active" : ""} onClick={() => setStatusFilter("open")} type="button"><span className="summary-icon"><TicketCheck /></span><span>Mới tạo</span><strong>{summary.open}</strong></button>
        <button aria-pressed={statusFilter === "in_progress"} className={statusFilter === "in_progress" ? "active" : ""} onClick={() => setStatusFilter("in_progress")} type="button"><span className="summary-icon amber"><Activity /></span><span>Đang xử lý</span><strong>{summary.in_progress}</strong></button>
        <button aria-label={`Chờ xác nhận: ${approvals.length}. Mở danh sách phê duyệt`} className="warning" onClick={openDraftPanel} type="button"><span className="summary-icon amber"><Clock3 /></span><span>Chờ xác nhận</span><strong>{approvals.length}</strong></button>
        <button aria-pressed={statusFilter === "resolved"} className={statusFilter === "resolved" ? "active" : ""} onClick={() => setStatusFilter("resolved")} type="button"><span className="summary-icon green"><CheckCircle2 /></span><span>Đã giải quyết</span><strong>{summary.resolved}</strong></button>
      </section>

      {draftOpen ? <button aria-label="Đóng bảng tạo ticket" className="ticket-drawer-backdrop" onClick={closeDraftPanel} type="button" /> : null}
      {draftOpen ? <aside aria-labelledby="ticket-draft-title" className="ticket-side-panel" ref={draftDialog} role="dialog">
      <section className="ticket-draft-panel">
        <header className="panel-header"><div><h2 id="ticket-draft-title">Tạo ticket hỗ trợ</h2><p>Gửi yêu cầu hỗ trợ tới đội ngũ IT.</p></div><button aria-label="Đóng panel tạo ticket" className="drawer-close" onClick={closeDraftPanel} type="button"><X aria-hidden="true" size={20} /></button></header>
        <form onSubmit={submitDraft}>
          <label>Tiêu đề<input minLength={5} ref={titleInput} required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          <label>Mô tả<textarea minLength={10} required rows={4} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
          <label>Loại sự cố<select aria-label="Loại sự cố" value={draft.issue_type} onChange={(event) => setDraft({ ...draft, issue_type: event.target.value as TicketDraftArguments["issue_type"] })}><option value="vpn">VPN</option><option value="docker">Docker</option><option value="gitlab">GitLab</option><option value="other">Khác</option></select></label>
          <label>Mức độ<select aria-label="Mức độ" value={draft.severity} onChange={(event) => setDraft({ ...draft, severity: event.target.value as TicketDraftArguments["severity"] })}><option value="low">Thấp</option><option value="normal">Bình thường</option><option value="high">Cao</option></select></label>
          <button className="primary-button" disabled={submitting} type="submit">{submitting ? "Đang tạo…" : "Tạo bản nháp"}</button>
        </form>
      </section>

      <section className="panel approvals-section">
        <header className="panel-header"><div><h2>Đang chờ xác nhận</h2><p>{approvals.length} thao tác cần quyết định</p></div></header>
        <div className="approval-grid">
          {approvals.length === 0 ? <EmptyState title="Không có thao tác đang chờ" description="Bản nháp mới sẽ xuất hiện ở đây để bạn kiểm tra." /> : null}
          {approvals.map((approval) => (
            <ApprovalCard
              approval={approval}
              key={approval.id}
              onDecision={(decision) => handleDecision(approval, decision)}
              onEdit={() => handleEdit(approval)}
            />
          ))}
        </div>
        {approvalCursor ? <button className="load-more-button" disabled={Boolean(loadingMore)} onClick={() => void loadMore("approvals")} type="button">{loadingMore === "approvals" ? "Đang tải…" : "Tải thêm phê duyệt"}</button> : null}
      </section>
      </aside> : null}

      <section className="panel ticket-library">
        <header className="panel-header"><div><h2>Ticket cá nhân</h2><p>{filteredTickets.length} kết quả đang hiển thị · {summary.total} ticket trong phạm vi của bạn</p></div></header>
        <div className="filter-bar">
          <label className="search-field"><Search aria-hidden="true" size={16} /><span className="sr-only">Tìm ticket</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo mã, tiêu đề…" type="search" value={query} /></label>
          <label><span className="sr-only">Lọc trạng thái</span><select aria-label="Lọc trạng thái" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="all">Mọi trạng thái</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option></select></label>
          <label><span className="sr-only">Lọc mức độ</span><select aria-label="Lọc mức độ" onChange={(event) => setSeverityFilter(event.target.value)} value={severityFilter}><option value="all">Mọi mức độ</option><option value="high">Cao</option><option value="normal">Bình thường</option><option value="low">Thấp</option></select></label>
          <label><span className="sr-only">Lọc loại sự cố</span><select aria-label="Lọc loại sự cố" onChange={(event) => setIssueTypeFilter(event.target.value)} value={issueTypeFilter}><option value="all">Mọi loại</option><option value="vpn">VPN</option><option value="docker">Docker</option><option value="gitlab">GitLab</option><option value="other">Khác</option></select></label>
        </div>
        {filteredTickets.length === 0 ? <EmptyState title={tickets.length === 0 ? "Chưa có ticket nào" : "Không tìm thấy ticket"} description={tickets.length === 0 ? "Tạo bản nháp để bắt đầu yêu cầu hỗ trợ." : "Thử thay đổi từ khóa hoặc bộ lọc."} /> : (
          <div className="table-scroll">
            <table className="data-table tickets-table">
              <thead><tr><th>Mã</th><th>Tiêu đề</th><th>Loại</th><th>Mức độ</th><th>Trạng thái</th><th>Cập nhật</th></tr></thead>
              <tbody>{filteredTickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td><strong>{ticket.display_key}</strong></td>
                  <td><Link className="ticket-title-link" to={`/tickets/${ticket.id}`}><strong>{ticket.title}</strong><small>{ticket.description}</small></Link></td>
                  <td>{formatIssueType(ticket.issue_type)}</td>
                  <td><StatusBadge value={ticket.severity} /></td>
                  <td><StatusBadge value={ticket.status} /></td>
                  <td>{formatRelativeTime(ticket.updated_at)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {ticketCursor ? <button className="load-more-button" disabled={Boolean(loadingMore)} onClick={() => void loadMore("tickets")} type="button">{loadingMore === "tickets" ? "Đang tải…" : "Tải thêm ticket"}</button> : null}
      </section>
    </div>
  );
}
