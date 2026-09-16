export interface TicketDraftArguments {
  title: string;
  description: string;
  issue_type: "vpn" | "docker" | "gitlab" | "other";
  severity: "low" | "normal" | "high";
  device_id: string | null;
}

export interface Approval {
  id: string;
  action_id: string;
  run_id: string;
  tool_name: string;
  canonical_args: TicketDraftArguments;
  arguments_hash: string;
  schema_version: number;
  status: "pending" | "approved" | "rejected" | "executed" | "expired";
  version: number;
  expires_at: string;
}

export interface Ticket {
  id: string;
  display_key: string;
  title: string;
  description: string;
  issue_type: string;
  severity: string;
  status: string;
  resolution_note: string | null;
  version: number;
}

export interface TicketDraftResponse {
  run_id: string;
  approval: Approval;
  created: boolean;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    credentials: "same-origin",
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(
      response.status === 409
        ? "Yêu cầu đã được xử lý hoặc đã hết hiệu lực."
        : "Không thể xử lý yêu cầu ticket.",
    );
  }
  return (await response.json()) as T;
}

export function listMyTickets(signal?: AbortSignal): Promise<Ticket[]> {
  return request("/api/v1/tickets/mine", { signal });
}

export function listPendingApprovals(signal?: AbortSignal): Promise<Approval[]> {
  return request("/api/v1/approvals?approval_status=pending", { signal });
}

export function createTicketDraft(
  values: TicketDraftArguments,
  csrfToken: string,
  clientRequestId: string = crypto.randomUUID(),
): Promise<TicketDraftResponse> {
  return request("/api/v1/tickets/drafts", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ ...values, client_request_id: clientRequestId }),
  });
}

export function decideApproval(
  approval: Approval,
  decision: "approve" | "reject",
  csrfToken: string,
): Promise<Approval> {
  return request(`/api/v1/approvals/${encodeURIComponent(approval.id)}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ decision, expected_version: approval.version }),
  });
}
