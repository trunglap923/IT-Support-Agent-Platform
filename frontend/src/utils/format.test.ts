import { describe, expect, it, vi } from "vitest";

import { formatDateTime, formatIssueType, formatRelativeTime, formatStatus } from "./format";

describe("formatters", () => {
  it("maps ticket and issue values to Vietnamese labels", () => {
    expect(formatStatus("waiting_approval")).toBe("Chờ xác nhận");
    expect(formatStatus("custom_state")).toBe("custom state");
    expect(formatIssueType("docker")).toBe("Docker");
  });

  it("formats relative times deterministically", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-01T08:00:00Z"));
    expect(formatRelativeTime("2026-10-01T07:55:00Z")).toBe("5 phút trước");
    expect(formatRelativeTime("2026-09-30T08:00:00Z")).toBe("Hôm qua");
    vi.useRealTimers();
  });

  it("gracefully handles legacy records without timestamps", () => {
    expect(formatDateTime("")).toBe("—");
    expect(formatRelativeTime("not-a-date")).toBe("—");
  });
});
