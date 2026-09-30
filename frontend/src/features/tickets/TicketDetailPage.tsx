import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { listMyTickets, type Ticket } from "../../api/tickets";
import { EmptyState, LoadingState, PageHeader, StatusBadge } from "../../components/ProductUI";

export function TicketDetailPage() {
  const { ticketId } = useParams();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void listMyTickets(controller.signal)
      .then((items) => setTicket(items.find((item) => item.id === ticketId) ?? null))
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải ticket.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [ticketId]);

  if (loading) return <LoadingState label="Đang tải chi tiết ticket…" />;
  if (error) return <div className="alert-banner error" role="alert">{error}</div>;
  if (!ticket) {
    return (
      <EmptyState
        title="Không tìm thấy ticket"
        description="Ticket không tồn tại hoặc không thuộc phạm vi bạn được phép xem."
        action={<Link className="secondary-button" to="/tickets">Quay lại danh sách</Link>}
      />
    );
  }

  return (
    <div className="ticket-detail-page">
      <div className="breadcrumb"><Link to="/tickets">Ticket</Link><span>/</span><strong>{ticket.display_key}</strong></div>
      <PageHeader
        title={ticket.title}
        description={`${ticket.display_key} · Yêu cầu hỗ trợ của bạn`}
        actions={<><StatusBadge value={ticket.severity} /><StatusBadge value={ticket.status} /></>}
      />
      <div className="ticket-detail-layout">
        <section className="panel ticket-work">
          <header className="panel-header"><div><h2>Nội dung yêu cầu</h2><p>Thông tin đã được gửi cho đội hỗ trợ.</p></div></header>
          <article>
            <div className="activity-avatar" aria-hidden="true">U</div>
            <div>
              <strong>Người yêu cầu</strong>
              <small>Mô tả ban đầu</small>
              <p>{ticket.description}</p>
            </div>
          </article>
          {ticket.resolution_note ? (
            <article>
              <div className="activity-avatar support" aria-hidden="true">IT</div>
              <div>
                <strong>IT Support</strong>
                <small>Ghi chú xử lý</small>
                <p>{ticket.resolution_note}</p>
              </div>
            </article>
          ) : (
            <div className="work-placeholder">Chưa có ghi chú xử lý mới.</div>
          )}
        </section>
        <aside className="panel ticket-context">
          <header className="panel-header"><div><h2>Chi tiết ticket</h2><p>Ngữ cảnh và trạng thái hiện tại.</p></div></header>
          <dl>
            <div><dt>Trạng thái</dt><dd><StatusBadge value={ticket.status} /></dd></div>
            <div><dt>Ưu tiên</dt><dd><StatusBadge value={ticket.severity} /></dd></div>
            <div><dt>Loại sự cố</dt><dd>{ticket.issue_type}</dd></div>
            <div><dt>Mã ticket</dt><dd>{ticket.display_key}</dd></div>
            <div><dt>Phiên bản</dt><dd>{ticket.version}</dd></div>
          </dl>
        </aside>
      </div>
    </div>
  );
}
