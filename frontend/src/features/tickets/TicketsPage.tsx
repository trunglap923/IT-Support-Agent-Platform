import { useEffect, useState, type FormEvent } from "react";

import {
  createTicketDraft,
  decideApproval,
  listMyTickets,
  listPendingApprovals,
  type Approval,
  type Ticket,
  type TicketDraftArguments,
} from "../../api/tickets";
import { useAuth } from "../auth/useAuth";
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

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      listMyTickets(controller.signal),
      listPendingApprovals(controller.signal),
    ])
      .then(([ticketItems, approvalItems]) => {
        setTickets(ticketItems);
        setApprovals(approvalItems);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải ticket.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

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

  if (loading) return <p>Đang tải ticket…</p>;

  return (
    <div className="tickets-page">
      <header className="section-heading">
        <p className="eyebrow">CONTROLLED ACTIONS</p>
        <h1>Ticket hỗ trợ của bạn</h1>
        <p>Tạo bản nháp trước; hệ thống chỉ ghi ticket sau khi bạn xác nhận.</p>
      </header>

      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <p className="chat-error" role="alert">{error}</p> : null}

      <section className="ticket-draft-panel">
        <h2>Tạo bản nháp</h2>
        <form onSubmit={submitDraft}>
          <label>Tiêu đề<input minLength={5} required value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
          <label>Mô tả<textarea minLength={10} required rows={4} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
          <label>Loại sự cố<select value={draft.issue_type} onChange={(event) => setDraft({ ...draft, issue_type: event.target.value as TicketDraftArguments["issue_type"] })}><option value="vpn">VPN</option><option value="docker">Docker</option><option value="gitlab">GitLab</option><option value="other">Khác</option></select></label>
          <label>Mức độ<select value={draft.severity} onChange={(event) => setDraft({ ...draft, severity: event.target.value as TicketDraftArguments["severity"] })}><option value="low">Thấp</option><option value="normal">Bình thường</option><option value="high">Cao</option></select></label>
          <button className="primary-button" disabled={submitting} type="submit">{submitting ? "Đang tạo…" : "Tạo bản nháp"}</button>
        </form>
      </section>

      <section>
        <h2>Đang chờ xác nhận</h2>
        <div className="approval-grid">
          {approvals.length === 0 ? <p>Không có thao tác đang chờ.</p> : null}
          {approvals.map((approval) => (
            <ApprovalCard approval={approval} key={approval.id} onDecision={(decision) => handleDecision(approval, decision)} />
          ))}
        </div>
      </section>

      <section>
        <h2>Ticket cá nhân</h2>
        <div className="ticket-list">
          {tickets.length === 0 ? <p>Chưa có ticket nào.</p> : null}
          {tickets.map((ticket) => (
            <article key={ticket.id}>
              <span>{ticket.display_key} · {ticket.status}</span>
              <h3>{ticket.title}</h3>
              <p>{ticket.description}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
