import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  requestJson,
  SESSION_EXPIRED_EVENT,
} from "./client";

describe("shared API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes Retry-After and notifies the auth provider on 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({ detail: "internal detail must not be rendered" }, {
          status: 401,
          headers: { "Retry-After": "12" },
        }),
      ),
    );
    const listener = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, listener, { once: true });

    await expect(requestJson("/api/private")).rejects.toEqual(
      expect.objectContaining<Partial<ApiError>>({
        status: 401,
        retryAfterSeconds: 12,
        message: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
      }),
    );
    expect(listener).toHaveBeenCalledOnce();
  });

  it("supports a caller abort without reporting a timeout", async () => {
    const caller = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        caller.abort();
        return new Promise((_resolve, reject) => {
          if (init.signal?.aborted) {
            reject(new DOMException("Aborted", "AbortError"));
            return;
          }
          init.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      }),
    );

    await expect(requestJson("/api/private", { signal: caller.signal })).rejects.toEqual(
      expect.objectContaining({ name: "AbortError" }),
    );
  });

  it("uses safe status-specific messages instead of raw server details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({ detail: "Traceback: secret" }, { status: 409 }),
      ),
    );
    await expect(requestJson("/api/resource")).rejects.toEqual(
      expect.objectContaining({
        message: "Dữ liệu đã thay đổi. Hãy tải lại và thử lại.",
      }),
    );
  });
});
