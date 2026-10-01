import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConversation,
  listConversations,
  submitMessage,
  submitMessageFeedback,
} from "./chat";

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
    const created = {
      id: "c1", title: "IT support", device_id: null,
      created_at: "2026-10-01T08:00:00Z", updated_at: "2026-10-01T08:00:00Z",
      preview: null, preview_at: null, preview_role: null,
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(created), { status: 201 })));
    await expect(createConversation("csrf-token")).resolves.toEqual(created);
  });

  it("unwraps the bounded cursor page used by list endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        items: [{
          id: "c1", title: "IT support", device_id: null,
          created_at: "2026-10-01T08:00:00Z", updated_at: "2026-10-01T08:00:00Z",
          preview: null, preview_at: null, preview_role: null,
        }],
        next_cursor: "opaque-next-page",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations()).resolves.toEqual([
      {
        id: "c1", title: "IT support", device_id: null,
        created_at: "2026-10-01T08:00:00Z", updated_at: "2026-10-01T08:00:00Z",
        preview: null, preview_at: null, preview_role: null,
      },
    ]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/conversations?limit=20",
      expect.objectContaining({ credentials: "same-origin" }),
    );
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
