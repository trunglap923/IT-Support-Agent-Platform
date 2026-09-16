import { useEffect, useState } from "react";

import {
  listServiceStates,
  listTicketQueue,
  transitionTicket,
  updateServiceState,
  type ServiceState,
} from "../../api/operations";
import type { Ticket } from "../../api/tickets";
import { useAuth } from "../auth/useAuth";

export function OperationsPage() {
  const { csrfToken, user } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [services, setServices] = useState<ServiceState[]>([]);
  const [resolutionNotes, setResolutionNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(user?.role !== "employee");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.role === "employee") {
      return;
    }
    const controller = new AbortController();
    void Promise.all([listTicketQueue(controller.signal), listServiceStates(controller.signal)])
      .then(([ticketItems, serviceItems]) => {
        setTickets(ticketItems);
        setServices(serviceItems);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải dữ liệu vận hành.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user?.role]);

  if (user?.role === "employee") {
    return <p className="chat-error" role="alert">Khu vực này chỉ dành cho IT hoặc quản trị viên.</p>;
  }
  if (loading) return <p>Đang tải hàng đợi IT…</p>;

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
      <header className="section-heading">
        <p className="eyebrow">IT OPERATIONS</p>
        <h1>Hàng đợi hỗ trợ</h1>
      </header>
      {error ? <p className="chat-error" role="alert">{error}</p> : null}

      <section>
        <h2>Trạng thái dịch vụ mô phỏng</h2>
        <div className="service-grid">
          {services.map((service) => (
            <article key={service.service_id}>
              <h3>{service.service_id}</h3>
              <select aria-label={`Trạng thái ${service.service_id}`} disabled={user?.role !== "admin"} value={service.status} onChange={(event) => setServices((current) => current.map((item) => item.service_id === service.service_id ? { ...item, status: event.target.value as ServiceState["status"] } : item))}>
                <option value="healthy">Healthy</option><option value="degraded">Degraded</option><option value="down">Down</option><option value="unknown">Unknown</option>
              </select>
              <input aria-label={`Thông báo ${service.service_id}`} disabled={user?.role !== "admin"} value={service.message} onChange={(event) => setServices((current) => current.map((item) => item.service_id === service.service_id ? { ...item, message: event.target.value } : item))} />
              {user?.role === "admin" ? <button onClick={() => void saveService(service)} type="button">Lưu</button> : <small>Chỉ quản trị viên được thay đổi trạng thái mô phỏng.</small>}
            </article>
          ))}
        </div>
      </section>

      <section>
        <h2>Ticket trong phạm vi</h2>
        <div className="ticket-list">
          {tickets.length === 0 ? <p>Hàng đợi trống.</p> : null}
          {tickets.map((ticket) => (
            <article key={ticket.id}>
              <span>{ticket.display_key} · {ticket.status} · {ticket.severity}</span>
              <h3>{ticket.title}</h3>
              <p>{ticket.description}</p>
              {ticket.status === "open" ? <button onClick={() => void moveTicket(ticket, "start")} type="button">Bắt đầu xử lý</button> : null}
              {ticket.status === "in_progress" ? (
                <div className="resolve-controls">
                  <input aria-label={`Ghi chú xử lý ${ticket.display_key}`} placeholder="Ghi chú xử lý bắt buộc" value={resolutionNotes[ticket.id] ?? ""} onChange={(event) => setResolutionNotes((current) => ({ ...current, [ticket.id]: event.target.value }))} />
                  <button disabled={!resolutionNotes[ticket.id]?.trim()} onClick={() => void moveTicket(ticket, "resolve")} type="button">Resolve</button>
                </div>
              ) : null}
              {ticket.status === "resolved" ? <button onClick={() => void moveTicket(ticket, "reopen")} type="button">Reopen</button> : null}
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
