import { afterEach, describe, expect, it, vi } from "vitest";

import { createConversation, submitMessage, submitMessageFeedback } from "./chat";

describe("chat API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sends CSRF and idempotency key when submitting a message", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ run_id: "run-1", status: "queued", created: true, enqueued: true, enqueue_error: null }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await submitMessage("conversation-1", "VPN error", "csrf-token", "request-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/conversations/conversation-1/messages",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
        body: JSON.stringify({ content: "VPN error", client_request_id: "request-1" }),
      }),
    );
  });

  it("creates a conversation through the protected endpoint", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "c1", title: "IT support" }), { status: 201 })));
    await expect(createConversation("csrf-token")).resolves.toEqual({ id: "c1", title: "IT support" });
  });

  it("sends owner feedback with CSRF protection", async () => {
    const feedback = {
      id: "feedback-1",
      message_id: "message-1",
      rating: "helpful",
      reason: null,
      comment: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(feedback), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      submitMessageFeedback("conversation-1", "message-1", "helpful", "csrf-token"),
    ).resolves.toEqual(feedback);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/conversations/conversation-1/messages/message-1/feedback",
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
        body: JSON.stringify({ rating: "helpful" }),
      }),
    );
  });
});
