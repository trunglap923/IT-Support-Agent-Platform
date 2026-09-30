import { useEffect, useMemo, useState } from "react";

import {
  listServiceStates,
  listTicketQueuePage,
  transitionTicket,
  updateServiceState,
  type ServiceState,
} from "../../api/operations";
import type { Ticket } from "../../api/tickets";
import { AccessDenied, EmptyState, LoadingState, PageHeader, StatusBadge } from "../../components/ProductUI";
import { useAuth } from "../auth/useAuth";

export function OperationsPage() {
  const { csrfToken, user } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [services, setServices] = useState<ServiceState[]>([]);
  const [resolutionNotes, setResolutionNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(user?.role !== "employee");
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [issueTypeFilter, setIssueTypeFilter] = useState("all");
  const [ticketCursor, setTicketCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    if (user?.role === "employee") {
      return;
    }
    const controller = new AbortController();
    void Promise.all([
      listTicketQueuePage(null, controller.signal, {
        ...(statusFilter !== "all" ? { ticket_status: statusFilter } : {}),
        ...(severityFilter !== "all" ? { severity: severityFilter } : {}),
        ...(issueTypeFilter !== "all" ? { issue_type: issueTypeFilter } : {}),
      }),
      listServiceStates(controller.signal),
    ])
      .then(([ticketPage, serviceItems]) => {
        setTickets(ticketPage.items);
        setTicketCursor(ticketPage.next_cursor);
        setServices(serviceItems);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải dữ liệu vận hành.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [issueTypeFilter, severityFilter, statusFilter, user?.role]);

  async function loadMoreTickets() {
    if (!ticketCursor || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    try {
      const page = await listTicketQueuePage(ticketCursor, undefined, {
        ...(statusFilter !== "all" ? { ticket_status: statusFilter } : {}),
        ...(severityFilter !== "all" ? { severity: severityFilter } : {}),
        ...(issueTypeFilter !== "all" ? { issue_type: issueTypeFilter } : {}),
      });
      setTickets((current) => [...current, ...page.items]);
      setTicketCursor(page.next_cursor);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải thêm ticket.");
    } finally {
      setLoadingMore(false);
    }
  }

  const filteredTickets = useMemo(() => tickets.filter((ticket) => {
    const matchesQuery = `${ticket.display_key} ${ticket.title} ${ticket.description}`
      .toLowerCase()
      .includes(query.toLowerCase());
    return matchesQuery
      && (statusFilter === "all" || ticket.status === statusFilter)
      && (severityFilter === "all" || ticket.severity === severityFilter)
      && (issueTypeFilter === "all" || ticket.issue_type === issueTypeFilter);
  }), [issueTypeFilter, query, severityFilter, statusFilter, tickets]);

  if (user?.role === "employee") {
    return <AccessDenied message="Khu vực này chỉ dành cho IT hoặc quản trị viên." />;
  }
  if (loading) return <LoadingState label="Đang tải hàng đợi IT…" />;

  async function moveTicket(ticket: Ticket, action: "start" | "resolve" | "reopen") {
    if (!csrfToken) return;
    setError(null);
    try {
      const updated = await transitionTicket(
        ticket,
        action,
        csrfToken,
        resolutionNotes[ticket.id],
      );
      setTickets((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật ticket.");
    }
  }

  async function saveService(service: ServiceState) {
    if (!csrfToken) return;
    setError(null);
    try {
      const updated = await updateServiceState(service, csrfToken);
      setServices((current) => current.map((item) => item.service_id === updated.service_id ? updated : item));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật dịch vụ.");
    }
  }

  return (
    <div className="operations-page">
      <PageHeader
        eyebrow="IT OPERATIONS"
        title="Hàng đợi hỗ trợ"
        description="Theo dõi tình trạng dịch vụ và xử lý ticket trong phạm vi được phân quyền."
      />
      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="panel operations-services">
        <header className="panel-header">
          <div><h2>Trạng thái dịch vụ mô phỏng</h2><p>{services.length} dịch vụ đang được theo dõi</p></div>
          {user?.role !== "admin" ? <span className="permission-note">Chỉ quản trị viên được thay đổi trạng thái mô phỏng.</span> : null}
        </header>
        {services.length === 0 ? (
          <EmptyState title="Chưa có dịch vụ" description="Trạng thái dịch vụ mô phỏng sẽ xuất hiện tại đây." />
        ) : (
          <div className="table-scroll">
            <span className="mobile-scroll-hint">Vuốt ngang để xem chi tiết →</span>
            <table className="data-table service-table">
              <thead><tr><th>Dịch vụ</th><th>Trạng thái</th><th>Thông báo</th><th>Cập nhật</th><th aria-label="Thao tác" /></tr></thead>
              <tbody>{services.map((service) => (
                <tr key={service.service_id}>
                  <td><strong>{service.service_id}</strong><small>Fault mode: {service.fault_mode}</small></td>
                  <td>
                    <div className="service-status-control">
                      <StatusBadge value={service.status} />
                      <select aria-label={`Trạng thái ${service.service_id}`} disabled={user?.role !== "admin"} value={service.status} onChange={(event) => setServices((current) => current.map((item) => item.service_id === service.service_id ? { ...item, status: event.target.value as ServiceState["status"] } : item))}>
                        <option value="healthy">Healthy</option><option value="degraded">Degraded</option><option value="down">Down</option><option value="unknown">Unknown</option>
                      </select>
                    </div>
                  </td>
                  <td><input aria-label={`Thông báo ${service.service_id}`} disabled={user?.role !== "admin"} value={service.message} onChange={(event) => setServices((current) => current.map((item) => item.service_id === service.service_id ? { ...item, message: event.target.value } : item))} /></td>
                  <td><time dateTime={service.updated_at}>{new Date(service.updated_at).toLocaleString("vi-VN")}</time></td>
                  <td>{user?.role === "admin" ? <button className="compact-button" onClick={() => void saveService(service)} type="button">Lưu</button> : null}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel operations-queue">
        <header className="panel-header"><div><h2>Ticket trong phạm vi</h2><p>{tickets.length} ticket được phép xử lý</p></div></header>
        <div className="filter-bar">
          <label className="search-field"><span className="sr-only">Tìm ticket trong hàng đợi</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo mã, tiêu đề…" type="search" value={query} /></label>
          <label><span className="sr-only">Lọc trạng thái</span><select aria-label="Lọc trạng thái hàng đợi" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="all">Mọi trạng thái</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option></select></label>
          <label><span className="sr-only">Lọc mức độ</span><select aria-label="Lọc mức độ hàng đợi" onChange={(event) => setSeverityFilter(event.target.value)} value={severityFilter}><option value="all">Mọi mức độ</option><option value="high">Cao</option><option value="normal">Bình thường</option><option value="low">Thấp</option></select></label>
          <label><span className="sr-only">Lọc loại sự cố</span><select aria-label="Lọc loại sự cố hàng đợi" onChange={(event) => setIssueTypeFilter(event.target.value)} value={issueTypeFilter}><option value="all">Mọi loại</option><option value="vpn">VPN</option><option value="docker">Docker</option><option value="gitlab">GitLab</option><option value="other">Khác</option></select></label>
        </div>
        {filteredTickets.length === 0 ? (
          <EmptyState title={tickets.length === 0 ? "Hàng đợi trống" : "Không tìm thấy ticket"} description={tickets.length === 0 ? "Ticket mới trong phạm vi sẽ xuất hiện tại đây." : "Thử thay đổi từ khóa hoặc bộ lọc."} />
        ) : (
          <div className="table-scroll">
            <span className="mobile-scroll-hint">Vuốt ngang để xem thao tác →</span>
            <table className="data-table operations-ticket-table">
              <thead><tr><th>Ticket</th><th>Trạng thái</th><th>Ưu tiên</th><th>Thao tác tiếp theo</th></tr></thead>
              <tbody>{filteredTickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td>
                    <small>{ticket.display_key} · {ticket.status} · {ticket.severity}</small>
                    <strong>{ticket.title}</strong>
                    <small>{ticket.description}</small>
                  </td>
                  <td><StatusBadge value={ticket.status} /></td>
                  <td><StatusBadge value={ticket.severity} /></td>
                  <td className="queue-actions">
                    {ticket.status === "open" ? <button className="primary-button" onClick={() => void moveTicket(ticket, "start")} type="button">Bắt đầu xử lý</button> : null}
                    {ticket.status === "in_progress" ? (
                      <div className="resolve-controls">
                        <input aria-label={`Ghi chú xử lý ${ticket.display_key}`} placeholder="Ghi chú xử lý bắt buộc" value={resolutionNotes[ticket.id] ?? ""} onChange={(event) => setResolutionNotes((current) => ({ ...current, [ticket.id]: event.target.value }))} />
                        <button className="primary-button" disabled={!resolutionNotes[ticket.id]?.trim()} onClick={() => void moveTicket(ticket, "resolve")} type="button">Resolve</button>
                      </div>
                    ) : null}
                    {ticket.status === "resolved" ? <button className="secondary-button" onClick={() => void moveTicket(ticket, "reopen")} type="button">Reopen</button> : null}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {ticketCursor ? <button className="load-more-button" disabled={loadingMore} onClick={() => void loadMoreTickets()} type="button">{loadingMore ? "Đang tải…" : "Tải thêm ticket"}</button> : null}
      </section>
    </div>
  );
}
