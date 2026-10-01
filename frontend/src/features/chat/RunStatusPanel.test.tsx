import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RunStatusPanel } from "./RunStatusPanel";

const { useRunEventsMock } = vi.hoisted(() => ({ useRunEventsMock: vi.fn() }));

vi.mock("./useRunEvents", () => ({ useRunEvents: useRunEventsMock }));

describe("RunStatusPanel", () => {
  it("forwards streamed text without listing transport delta events", () => {
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
          type: "run.running",
          timestamp: "2026-09-16T00:00:00Z",
          payload: {},
        },
        {
          sequence: 3,
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

    expect(screen.getByRole("heading", { name: "Đang xử lý" })).toBeInTheDocument();
    expect(screen.getByText("run.running")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.queryByText("assistant.stream.delta")).not.toBeInTheDocument();
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
