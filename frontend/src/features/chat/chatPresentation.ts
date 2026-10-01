export type ConversationGroup = "Hôm nay" | "Hôm qua" | "7 ngày qua" | "Cũ hơn";

export function conversationActivityAt(conversation: {
  preview_at: string | null;
  updated_at: string;
  created_at: string;
}): string {
  return conversation.preview_at ?? conversation.updated_at ?? conversation.created_at;
}

export function groupConversationDate(value: string, now = new Date()): ConversationGroup {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "Cũ hơn";

  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const daysAgo = Math.floor((startOfToday.getTime() - startOfDate.getTime()) / 86_400_000);
  if (daysAgo <= 0) return "Hôm nay";
  if (daysAgo === 1) return "Hôm qua";
  if (daysAgo < 7) return "7 ngày qua";
  return "Cũ hơn";
}

export function formatChatTime(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit" }).format(date);
}

export function formatConversationDate(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" }).format(date);
}
