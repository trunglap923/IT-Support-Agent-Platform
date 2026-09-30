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
    { label: "Ticket đang mở", value: tickets.filter((ticket) => ticket.status === "open").length, icon: "▤", tone: "blue" },
    { label: "Đang xử lý", value: tickets.filter((ticket) => ticket.status === "in_progress").length, icon: "⚙", tone: "amber" },
    { label: "Chờ xác nhận", value: pendingApprovals, icon: "◷", tone: "red" },
    { label: "Đã giải quyết", value: tickets.filter((ticket) => ticket.status === "resolved").length, icon: "✓", tone: "green" },
  ], [pendingApprovals, tickets]);

  const attention = tickets
    .filter((ticket) => ticket.status !== "resolved")
    .sort((left, right) => (right.severity === "high" ? 1 : 0) - (left.severity === "high" ? 1 : 0))
    .slice(0, 5);

  return (
    <div className="dashboard-page">
      <PageHeader
        title="Tổng quan"
        description={`Theo dõi hoạt động IT Support của ${user?.display_name ?? "workspace"} trong thời gian thực.`}
        actions={<select aria-label="Khoảng thời gian" defaultValue="7"><option value="7">7 ngày qua</option><option value="30">30 ngày qua</option></select>}
      />

      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="metrics-strip" aria-label="Tổng quan ticket">
        {metrics.map((metric) => (
          <div className={`metric ${metric.tone}`} key={metric.label}>
            <span className="metric-icon" aria-hidden="true">{metric.icon}</span>
            <span className="metric-copy"><span>{metric.label}</span><strong>{loading ? "—" : metric.value}</strong><small>Dữ liệu hiện tại</small></span>
          </div>
        ))}
      </section>

      <div className="dashboard-grid">
        <section className="panel dashboard-breakdown">
          <header className="panel-header"><div><h2>Phân bổ ticket hiện tại</h2><p>Theo trạng thái trong phạm vi của bạn.</p></div><Link className="text-link" to="/tickets">Xem tất cả →</Link></header>
          <div className="breakdown-bars">
            {metrics.filter((metric) => metric.label !== "Chờ xác nhận").map((metric) => {
              const maximum = Math.max(1, ...metrics.map((item) => item.value));
              return <div className={`breakdown-row ${metric.tone}`} key={metric.label}><span>{metric.label}</span><div><i style={{ width: `${Math.max(8, metric.value / maximum * 100)}%` }} /></div><strong>{metric.value}</strong></div>;
            })}
          </div>
        </section>

        <aside className="dashboard-aside dashboard-status-aside">
          <section className="panel system-panel">
            <header className="panel-header"><div><h2>Trạng thái hệ thống</h2><p>Kết nối dịch vụ hiện tại.</p></div></header>
            <HealthStatus />
          </section>
        </aside>

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
