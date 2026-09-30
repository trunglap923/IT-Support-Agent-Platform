import { describe, expect, it, vi } from "vitest";

import { getOrCreateClientRequest } from "./idempotency";

describe("getOrCreateClientRequest", () => {
  it("reuses the id when the same payload is retried", () => {
    const createId = vi.fn(() => "request-1");
    const first = getOrCreateClientRequest(null, "payload-1", createId);
    const retry = getOrCreateClientRequest(first, "payload-1", createId);

    expect(retry).toBe(first);
    expect(createId).toHaveBeenCalledOnce();
  });

  it("creates a new id after the payload changes", () => {
    const createId = vi.fn()
      .mockReturnValueOnce("request-1")
      .mockReturnValueOnce("request-2");
    const first = getOrCreateClientRequest(null, "payload-1", createId);
    const changed = getOrCreateClientRequest(first, "payload-2", createId);

    expect(changed.id).toBe("request-2");
    expect(createId).toHaveBeenCalledTimes(2);
  });
});
