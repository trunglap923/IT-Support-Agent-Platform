import type { Ticket } from "./tickets";
import { requestJson } from "./client";
import type { CursorPage } from "./pagination";
import { paginatedUrl } from "./pagination";

export interface ServiceState {
  service_id: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  message: string;
  fault_mode: "none" | "timeout" | "error";
  updated_at: string;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  return requestJson(url, {
    ...init,
    messages: {
      fallback: "Không thể xử lý yêu cầu vận hành.",
      byStatus: {
        403: "Bạn không có quyền thực hiện thao tác này.",
        409: "Dữ liệu đã thay đổi. Hãy tải lại trang.",
      },
    },
  });
}

export async function listTicketQueue(signal?: AbortSignal): Promise<Ticket[]> {
  const page = await request<CursorPage<Ticket>>(paginatedUrl("/api/v1/tickets/queue"), {
    signal,
  });
  return page.items;
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
