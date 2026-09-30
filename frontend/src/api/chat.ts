export interface Conversation {
  id: string;
  title: string;
}

export interface ChatCitation {
  source_id: string;
  source_url?: string;
  document_id?: string;
  title: string;
  page_number: number | null;
  excerpt: string;
}

export interface ChatMessage {
  id: string;
  run_id: string | null;
  role: "user" | "assistant";
  content: string;
  outcome: string | null;
  citations?: ChatCitation[];
  feedback?: MessageFeedback | null;
}

export interface MessageFeedback {
  id: string;
  message_id: string;
  rating: "helpful" | "unhelpful";
  reason: string | null;
  comment: string | null;
}

export interface SubmittedRun {
  run_id: string;
  status: string;
  created: boolean;
  enqueued: boolean;
  enqueue_error: string | null;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  return requestJson(url, {
    ...init,
    messages: {
      fallback: "Không thể xử lý yêu cầu chat.",
      byStatus: {
        409: "Cuộc trò chuyện đang xử lý một yêu cầu khác.",
        503: "Worker đang tạm thời không sẵn sàng.",
      },
    },
  });
}

export function listConversationsPage(
  cursor: string | null = null,
  signal?: AbortSignal,
): Promise<CursorPage<Conversation>> {
  return request(paginatedUrl("/api/v1/conversations", {}, cursor), { signal });
}

export async function listConversations(signal?: AbortSignal): Promise<Conversation[]> {
  return (await listConversationsPage(null, signal)).items;
}

export function listMessagesPage(
  conversationId: string,
  cursor: string | null = null,
  signal?: AbortSignal,
): Promise<CursorPage<ChatMessage>> {
  return request(
    paginatedUrl(
      `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
      {},
      cursor,
    ),
    { signal },
  );
}

export async function listMessages(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ChatMessage[]> {
  return (await listMessagesPage(conversationId, null, signal)).items;
}

export function createConversation(
  csrfToken: string,
  title = "IT support",
): Promise<Conversation> {
  return request("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ title }),
  });
}

export function submitMessage(
  conversationId: string,
  content: string,
  csrfToken: string,
  clientRequestId: string = crypto.randomUUID(),
): Promise<SubmittedRun> {
  return request(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ content, client_request_id: clientRequestId }),
    },
  );
}

export function submitMessageFeedback(
  conversationId: string,
  messageId: string,
  rating: MessageFeedback["rating"],
  csrfToken: string,
): Promise<MessageFeedback> {
  return request(
    `/api/v1/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/feedback`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ rating }),
    },
  );
}
import { requestJson } from "./client";
import type { CursorPage } from "./pagination";
import { paginatedUrl } from "./pagination";
