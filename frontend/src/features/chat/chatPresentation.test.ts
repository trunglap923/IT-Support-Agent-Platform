import { describe, expect, it } from "vitest";

import { formatChatTime, groupConversationDate } from "./chatPresentation";

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
});
