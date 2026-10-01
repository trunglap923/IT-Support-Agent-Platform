import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RunStatusPanel } from "./RunStatusPanel";

const { useRunEventsMock } = vi.hoisted(() => ({ useRunEventsMock: vi.fn() }));

vi.mock("./useRunEvents", () => ({ useRunEvents: useRunEventsMock }));

describe("RunStatusPanel", () => {
  it("shows safe progress labels and expands the activity timeline", () => {
    const onStatus = vi.fn();
    const onStreamText = vi.fn();
    useRunEventsMock.mockReturnValue({
      snapshot: { status: "running" },
      connectionState: "open",
      error: null,
      retry: vi.fn(),
      streamedText: "Use SSO.",
      events: [
        {
          sequence: 2,
          run_id: "run-1",
          type: "agent.progress",
          timestamp: "2026-09-16T00:00:00Z",
          payload: { stage: "analyze", status: "completed", detail: "Đã xác định nội dung cần hỗ trợ." },
        },
        {
          sequence: 3,
          run_id: "run-1",
          type: "agent.progress",
          timestamp: "2026-09-16T00:00:01Z",
          payload: { stage: "device", status: "started" },
        },
        {
          sequence: 4,
          run_id: "run-1",
          type: "assistant.stream.delta",
          timestamp: "2026-09-16T00:00:01Z",
          payload: { delta: "Use SSO." },
        },
      ],
    });

    render(
      <RunStatusPanel
        onStatus={onStatus}
        onStreamText={onStreamText}
        runId="run-1"
      />,
    );

    expect(screen.getByRole("heading", { name: "Đang xử lý yêu cầu của bạn…" })).toBeInTheDocument();
    expect(screen.getByText("Kiểm tra thông tin thiết bị")).toBeInTheDocument();
    expect(screen.queryByText("agent.progress")).not.toBeInTheDocument();
    expect(screen.queryByText("assistant.stream.delta")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Xem chi tiết" }));
    expect(screen.getByText("Phân tích yêu cầu")).toBeInTheDocument();
    expect(screen.getByText("Đã xác định nội dung cần hỗ trợ.")).toBeInTheDocument();
    expect(onStatus).toHaveBeenCalledWith("running");
    expect(onStreamText).toHaveBeenCalledWith("Use SSO.");
  });

  it("notifies a status once when parent callbacks change", () => {
    const onStatus = vi.fn();
    useRunEventsMock.mockReturnValue({
      snapshot: { status: "waiting_approval" },
      connectionState: "open",
      error: null,
      retry: vi.fn(),
      events: [],
    });

    const { rerender } = render(
      <RunStatusPanel onStatus={onStatus} onTerminal={() => undefined} runId="run-1" />,
    );
    rerender(
      <RunStatusPanel onStatus={onStatus} onTerminal={() => undefined} runId="run-1" />,
    );

    expect(onStatus).toHaveBeenCalledOnce();
  });

  it("renders only the stages planned for a profile question", () => {
    useRunEventsMock.mockReturnValue({
      snapshot: { status: "running" },
      connectionState: "open",
      error: null,
      retry: vi.fn(),
      streamedText: "",
      events: [
        {
          sequence: 1,
          run_id: "run-profile",
          type: "agent.progress",
          timestamp: "2026-10-01T00:00:00Z",
          payload: { stage: "analyze", status: "completed" },
        },
        {
          sequence: 2,
          run_id: "run-profile",
          type: "agent.progress",
          timestamp: "2026-10-01T00:00:01Z",
          payload: { stage: "profile", status: "started", detail: "Đang đọc thông tin tài khoản." },
        },
        {
          sequence: 3,
          run_id: "run-profile",
          type: "agent.progress",
          timestamp: "2026-10-01T00:00:01Z",
          payload: { stage: "answer", status: "pending" },
        },
      ],
    });

    render(<RunStatusPanel runId="run-profile" />);
    expect(screen.getByText("Đọc thông tin tài khoản")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Xem chi tiết" }));
    expect(screen.queryByText("Kiểm tra thông tin thiết bị")).not.toBeInTheDocument();
    expect(screen.queryByText("Tìm kiếm kho tri thức")).not.toBeInTheDocument();
    expect(screen.getByText("Tổng hợp hướng xử lý")).toBeInTheDocument();
  });

  it("offers an explicit retry after the reconnect budget is exhausted", () => {
    const retry = vi.fn();
    useRunEventsMock.mockReturnValue({
      snapshot: null,
      connectionState: "closed",
      error: "Mất kết nối tới luồng trạng thái run.",
      retry,
      events: [],
    });

    render(<RunStatusPanel runId="run-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Thử kết nối lại" }));

    expect(retry).toHaveBeenCalledOnce();
  });
});
