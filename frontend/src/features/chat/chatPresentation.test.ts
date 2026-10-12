import { describe, expect, it } from "vitest";

import { formatChatTime, getSupportQuickActions, groupConversationDate } from "./chatPresentation";

describe("chat presentation helpers", () => {
  const now = new Date("2026-10-01T10:00:00");

  it("groups conversation activity by local day", () => {
    expect(groupConversationDate("2026-10-01T08:00:00", now)).toBe("Hôm nay");
    expect(groupConversationDate("2026-09-30T08:00:00", now)).toBe("Hôm qua");
    expect(groupConversationDate("2026-09-27T08:00:00", now)).toBe("7 ngày qua");
    expect(groupConversationDate("2026-09-20T08:00:00", now)).toBe("Cũ hơn");
  });

  it("formats message times and handles invalid input", () => {
    expect(formatChatTime("not-a-date")).toBe("—");
    expect(formatChatTime("2026-10-01T08:05:00")).toMatch(/08:05/);
  });

  it("uses the latest explicit support topic for quick actions", () => {
    expect(getSupportQuickActions("VPN không kết nối", [
      { role: "user", content: "VPN của tôi bị lỗi" },
      { role: "assistant", content: "Hãy kiểm tra kết nối mạng." },
      { role: "user", content: "Tôi cần được cấp quyền GitLab" },
    ])).toEqual([
      "Hướng dẫn xử lý truy cập GitLab",
      "Kiểm tra quyền truy cập GitLab",
      "Tạo ticket hỗ trợ",
    ]);
  });

  it("falls back to the conversation topic for a short follow-up", () => {
    expect(getSupportQuickActions("Docker registry", [
      { role: "user", content: "Nó vẫn báo lỗi thì làm sao?" },
    ])[0]).toBe("Hướng dẫn kiểm tra Docker/registry");
  });
});
