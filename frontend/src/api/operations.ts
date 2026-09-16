import type { Ticket } from "./tickets";

export interface ServiceState {
  service_id: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  message: string;
  fault_mode: "none" | "timeout" | "error";
  updated_at: string;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(
      response.status === 403
        ? "Bạn không có quyền thực hiện thao tác này."
        : response.status === 409
          ? "Dữ liệu đã thay đổi. Hãy tải lại trang."
          : "Không thể xử lý yêu cầu vận hành.",
    );
  }
  return (await response.json()) as T;
}

export function listTicketQueue(signal?: AbortSignal): Promise<Ticket[]> {
  return request("/api/v1/tickets/queue", { signal });
}

export function transitionTicket(
  ticket: Ticket,
  action: "start" | "resolve" | "reopen",
  csrfToken: string,
  resolutionNote?: string,
): Promise<Ticket> {
  return request(`/api/v1/tickets/${encodeURIComponent(ticket.id)}/transition`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({
      action,
      expected_version: ticket.version,
      resolution_note: resolutionNote ?? null,
    }),
  });
}

export function listServiceStates(signal?: AbortSignal): Promise<ServiceState[]> {
  return request("/api/v1/service-status", { signal });
}

export function updateServiceState(
  service: ServiceState,
  csrfToken: string,
): Promise<ServiceState> {
  return request(`/api/v1/service-status/${encodeURIComponent(service.service_id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({
      status: service.status,
      message: service.message,
      fault_mode: service.fault_mode,
    }),
  });
}
