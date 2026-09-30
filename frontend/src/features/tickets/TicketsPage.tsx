import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { cancelRun, getRunSnapshot } from "../../api/run-events";
import {
  createTicketDraft,
  decideApproval,
  listMyTicketsPage,
  listPendingApprovalsPage,
  type Approval,
  type Ticket,
  type TicketDraftArguments,
} from "../../api/tickets";
import { useAuth } from "../auth/useAuth";
import { EmptyState, LoadingState, PageHeader, StatusBadge } from "../../components/ProductUI";
import { ApprovalCard } from "./ApprovalCard";

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
  const titleInput = useRef<HTMLInputElement>(null);
  const draftPanel = useRef<HTMLElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      listMyTicketsPage(null, controller.signal, {
        ...(statusFilter !== "all" ? { ticket_status: statusFilter } : {}),
        ...(severityFilter !== "all" ? { severity: severityFilter } : {}),
        ...(issueTypeFilter !== "all" ? { issue_type: issueTypeFilter } : {}),
      }),
      listPendingApprovalsPage(null, controller.signal),
    ])
      .then(([ticketPage, approvalPage]) => {
        setTickets(ticketPage.items);
        setTicketCursor(ticketPage.next_cursor);
        setApprovals(approvalPage.items);
        setApprovalCursor(approvalPage.next_cursor);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải ticket.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [issueTypeFilter, severityFilter, statusFilter]);

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
      const created = await createTicketDraft(draft, csrfToken);
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

  if (loading) return <LoadingState label="Đang tải ticket…" />;

  return (
    <div className="tickets-page">
      <PageHeader
        eyebrow="TICKET MANAGEMENT"
        title="Ticket hỗ trợ"
        description="Theo dõi yêu cầu và xác nhận rõ nội dung trước khi tạo ticket."
        actions={<button className="primary-button" onClick={() => { draftPanel.current?.scrollIntoView({ behavior: "smooth" }); titleInput.current?.focus(); }} type="button">+ Tạo ticket</button>}
      />

      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="panel ticket-draft-panel" ref={draftPanel}>
        <header className="panel-header"><div><h2>Tạo bản nháp</h2><p>Ticket chỉ được ghi sau bước xác nhận.</p></div></header>
        <form onSubmit={submitDraft}>
          <label>Tiêu đề<input minLength={5} ref={titleInput} required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          <label>Mô tả<textarea minLength={10} required rows={4} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
          <label>Loại sự cố<select value={draft.issue_type} onChange={(event) => setDraft({ ...draft, issue_type: event.target.value as TicketDraftArguments["issue_type"] })}><option value="vpn">VPN</option><option value="docker">Docker</option><option value="gitlab">GitLab</option><option value="other">Khác</option></select></label>
          <label>Mức độ<select value={draft.severity} onChange={(event) => setDraft({ ...draft, severity: event.target.value as TicketDraftArguments["severity"] })}><option value="low">Thấp</option><option value="normal">Bình thường</option><option value="high">Cao</option></select></label>
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

      <section className="panel">
        <header className="panel-header"><div><h2>Ticket cá nhân</h2><p>{tickets.length} ticket trong phạm vi của bạn</p></div></header>
        <div className="filter-bar">
          <label className="search-field"><span className="sr-only">Tìm ticket</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo mã, tiêu đề…" type="search" value={query} /></label>
          <label><span className="sr-only">Lọc trạng thái</span><select aria-label="Lọc trạng thái" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="all">Mọi trạng thái</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option></select></label>
          <label><span className="sr-only">Lọc mức độ</span><select aria-label="Lọc mức độ" onChange={(event) => setSeverityFilter(event.target.value)} value={severityFilter}><option value="all">Mọi mức độ</option><option value="high">Cao</option><option value="normal">Bình thường</option><option value="low">Thấp</option></select></label>
          <label><span className="sr-only">Lọc loại sự cố</span><select aria-label="Lọc loại sự cố" onChange={(event) => setIssueTypeFilter(event.target.value)} value={issueTypeFilter}><option value="all">Mọi loại</option><option value="vpn">VPN</option><option value="docker">Docker</option><option value="gitlab">GitLab</option><option value="other">Khác</option></select></label>
        </div>
        {filteredTickets.length === 0 ? <EmptyState title={tickets.length === 0 ? "Chưa có ticket nào" : "Không tìm thấy ticket"} description={tickets.length === 0 ? "Tạo bản nháp để bắt đầu yêu cầu hỗ trợ." : "Thử thay đổi từ khóa hoặc bộ lọc."} /> : (
          <div className="table-scroll">
            <table className="data-table tickets-table">
              <thead><tr><th>Mã</th><th>Tiêu đề</th><th>Trạng thái</th><th>Ưu tiên</th><th>Loại</th></tr></thead>
              <tbody>{filteredTickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td><strong>{ticket.display_key}</strong></td>
                  <td><Link className="ticket-title-link" to={`/tickets/${ticket.id}`}><strong>{ticket.title}</strong><small>{ticket.description}</small></Link></td>
                  <td><StatusBadge value={ticket.status} /></td>
                  <td><StatusBadge value={ticket.severity} /></td>
                  <td>{ticket.issue_type}</td>
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
