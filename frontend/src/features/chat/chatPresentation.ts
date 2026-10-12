export type ConversationGroup = "Hôm nay" | "Hôm qua" | "7 ngày qua" | "Cũ hơn";

type TopicMessage = {
  role: string;
  content: string;
};

const genericQuickActions = ["Tóm tắt hướng xử lý", "Hỏi thêm về sự cố này", "Tạo ticket hỗ trợ"];

function supportTopic(value: string): "vpn" | "docker" | "gitlab" | null {
  const normalized = value.toLocaleLowerCase();
  if (normalized.includes("vpn")) return "vpn";
  if (normalized.includes("docker") || normalized.includes("registry")) return "docker";
  if (normalized.includes("gitlab")) return "gitlab";
  return null;
}

export function getSupportQuickActions(
  conversationTitle: string | undefined,
  messages: TopicMessage[],
): string[] {
  let latestUserMessage: TopicMessage | undefined;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === "user") {
      latestUserMessage = messages[index];
      break;
    }
  }

  const topic = supportTopic(latestUserMessage?.content ?? "")
    ?? supportTopic(conversationTitle ?? "");
  if (topic === "vpn") {
    return ["Kiểm tra trạng thái dịch vụ VPN", "Hướng dẫn khắc phục lỗi VPN", "Tạo ticket hỗ trợ"];
  }
  if (topic === "docker") {
    return ["Hướng dẫn kiểm tra Docker/registry", "Kiểm tra lỗi Docker gần nhất", "Tạo ticket hỗ trợ"];
  }
  if (topic === "gitlab") {
    return ["Hướng dẫn xử lý truy cập GitLab", "Kiểm tra quyền truy cập GitLab", "Tạo ticket hỗ trợ"];
  }
  return genericQuickActions;
}

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
