import { describe, expect, it, vi } from "vitest";

import { consumeRunEvents, parseSseFrame, RunStreamError } from "./run-events";

function streamResponse(body: string): Response {
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function snapshotResponse(status: string): Response {
  return Response.json({
    id: "run-1",
    conversation_id: "conversation-1",
    status,
    outcome: null,
    version: 1,
    error_code: null,
  });
}

describe("run event client", () => {
  it("parses comments, IDs and multiline data", () => {
    expect(parseSseFrame(": heartbeat\r\nid: 4\r\nevent: run\r\ndata: {\r\ndata: }"))
      .toEqual({ id: "4", event: "run", data: "{\n}" });
  });

  it("reconnects without creating a run and resumes from the last event ID", async () => {
    const onEvent = vi.fn();
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        streamResponse(
          'id: 3\r\nevent: run\r\ndata: {"sequence":3,"run_id":"run-1","type":"run.running","timestamp":"2026-09-16T00:00:00Z","payload":{}}\r\n\r\n',
        ),
      )
      .mockResolvedValueOnce(snapshotResponse("running"))
      .mockResolvedValueOnce(
        streamResponse(
          'id: 4\nevent: run\ndata: {"sequence":4,"run_id":"run-1","type":"run.completed","timestamp":"2026-09-16T00:00:01Z","payload":{}}\n\n',
        ),
      )
      .mockResolvedValueOnce(snapshotResponse("completed"));

    const result = await consumeRunEvents("run-1", {
      signal: new AbortController().signal,
      onEvent,
      fetchImpl: fetchMock,
      waitImpl: vi.fn().mockResolvedValue(undefined),
    });

    expect(result.status).toBe("completed");
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/v1/runs/run-1/events?after_sequence=3",
      expect.objectContaining({ headers: expect.objectContaining({ "Last-Event-ID": "3" }) }),
    );
  });

  it("does not retry authorization or missing-run failures", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 404 }));

    await expect(
      consumeRunEvents("unknown", {
        signal: new AbortController().signal,
        onEvent: vi.fn(),
        fetchImpl: fetchMock,
      }),
    ).rejects.toEqual(expect.objectContaining<Partial<RunStreamError>>({ status: 404 }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
