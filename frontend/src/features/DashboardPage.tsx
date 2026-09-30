import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listPendingApprovals, listMyTickets, type Ticket } from "../api/tickets";
import { HealthStatus } from "../components/HealthStatus";
import { EmptyState, PageHeader, StatusBadge } from "../components/ProductUI";
import { useAuth } from "./auth/useAuth";

export function DashboardPage() {
  const { user } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      listMyTickets(controller.signal),
      listPendingApprovals(controller.signal),
    ])
      .then(([ticketItems, approvalItems]) => {
        setTickets(ticketItems);
        setPendingApprovals(approvalItems.length);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải dữ liệu tổng quan.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const metrics = useMemo(() => [
    { label: "Ticket đang mở", value: tickets.filter((ticket) => ticket.status === "open").length },
    { label: "Đang xử lý", value: tickets.filter((ticket) => ticket.status === "in_progress").length },
    { label: "Chờ xác nhận", value: pendingApprovals },
    { label: "Đã giải quyết", value: tickets.filter((ticket) => ticket.status === "resolved").length },
  ], [pendingApprovals, tickets]);

  const attention = tickets
    .filter((ticket) => ticket.status !== "resolved")
    .sort((left, right) => (right.severity === "high" ? 1 : 0) - (left.severity === "high" ? 1 : 0))
    .slice(0, 5);

  return (
    <div className="dashboard-page">
      <PageHeader
        eyebrow="WORKSPACE OVERVIEW"
        title={`Chào ${user?.display_name?.split(" ")[0] ?? "bạn"}`}
        description="Theo dõi các yêu cầu cần chú ý và tiếp tục công việc hỗ trợ từ một nơi."
        actions={<Link className="primary-button" to="/chat">Hỏi trợ lý AI</Link>}
      />

      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="metrics-strip" aria-label="Tổng quan ticket">
        {metrics.map((metric) => (
          <div className="metric" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{loading ? "—" : metric.value}</strong>
          </div>
        ))}
      </section>

      <div className="dashboard-grid">
        <section className="panel">
          <header className="panel-header">
            <div>
              <h2>Cần chú ý</h2>
              <p>Ticket đang mở hoặc đang được xử lý.</p>
            </div>
            <Link className="text-link" to="/tickets">Xem tất cả</Link>
          </header>
          {attention.length === 0 && !loading ? (
            <EmptyState title="Không có ticket tồn đọng" description="Các ticket mới cần xử lý sẽ xuất hiện tại đây." />
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>Ticket</th><th>Trạng thái</th><th>Ưu tiên</th></tr></thead>
                <tbody>
                  {attention.map((ticket) => (
                    <tr key={ticket.id}>
                      <td><strong>{ticket.display_key}</strong><small>{ticket.title}</small></td>
                      <td><StatusBadge value={ticket.status} /></td>
                      <td><StatusBadge value={ticket.severity} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="dashboard-aside">
          <section className="panel system-panel">
            <header className="panel-header"><div><h2>Trạng thái hệ thống</h2><p>Kết nối backend hiện tại.</p></div></header>
            <HealthStatus />
          </section>
          <section className="panel quick-actions">
            <header className="panel-header"><div><h2>Thao tác nhanh</h2><p>Tiếp tục luồng công việc thường dùng.</p></div></header>
            <Link to="/chat"><strong>Khắc phục sự cố</strong><span>Hỏi đáp dựa trên tài liệu nội bộ</span></Link>
            <Link to="/tickets"><strong>Tạo ticket</strong><span>Soạn nháp và xác nhận trước khi gửi</span></Link>
            <Link to="/settings/memory"><strong>Kiểm tra memory</strong><span>Quản lý fact và thiết bị đã xác nhận</span></Link>
          </section>
        </aside>
      </div>
    </div>
  );
}
