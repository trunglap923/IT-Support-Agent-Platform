import { describe, expect, it } from "vitest";

import type { RunEventData } from "../../api/run-events";
import { streamedTextAfterEvent } from "./useRunEvents";

function event(type: string, payload: Record<string, unknown> = {}): RunEventData {
  return {
    sequence: 1,
    run_id: "run-1",
    type,
    timestamp: "2026-10-01T00:00:00Z",
    payload,
  };
}

describe("streamedTextAfterEvent", () => {
  it("appends answer deltas in order", () => {
    const first = streamedTextAfterEvent("", event("assistant.stream.delta", { delta: "Xin " }));
    const second = streamedTextAfterEvent(
      first,
      event("assistant.stream.delta", { delta: "chào" }),
    );

    expect(second).toBe("Xin chào");
  });

  it("resets the draft when a new generation starts", () => {
    expect(streamedTextAfterEvent("old answer", event("assistant.stream.started"))).toBe("");
  });

  it("ignores unrelated events and invalid payloads", () => {
    expect(streamedTextAfterEvent("kept", event("run.running"))).toBe("kept");
    expect(
      streamedTextAfterEvent("kept", event("assistant.stream.delta", { delta: 42 })),
    ).toBe("kept");
  });
});
