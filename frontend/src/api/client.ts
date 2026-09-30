export const SESSION_EXPIRED_EVENT = "it-support:session-expired";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly retryAfterSeconds: number | null = null,
    public readonly code: string | null = null,
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestMessages {
  fallback?: string;
  byStatus?: Partial<Record<number, string>>;
}

export interface ApiRequestInit extends RequestInit {
  timeoutMs?: number;
  messages?: RequestMessages;
  notifyOnUnauthorized?: boolean;
}

const defaultMessages: Record<number, string> = {
  401: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
  403: "Bạn không có quyền thực hiện thao tác này.",
  404: "Không tìm thấy dữ liệu được yêu cầu.",
  409: "Dữ liệu đã thay đổi. Hãy tải lại và thử lại.",
  410: "Dữ liệu này không còn khả dụng.",
  413: "Dữ liệu tải lên vượt quá giới hạn cho phép.",
  422: "Dữ liệu gửi lên không hợp lệ.",
  429: "Bạn thao tác quá nhanh. Vui lòng chờ rồi thử lại.",
  503: "Dịch vụ đang tạm thời không sẵn sàng.",
};

export function notifySessionExpired(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
}

function retryAfterSeconds(response: Response): number | null {
  const raw = response.headers.get("Retry-After");
  if (!raw) return null;
  const seconds = Number(raw);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

async function responseError(
  response: Response,
  messages?: RequestMessages,
): Promise<ApiError> {
  // Read diagnostic identifiers, but never render arbitrary backend messages.
  const payload = await response.json().catch(() => null) as {
    error?: { code?: unknown; request_id?: unknown };
  } | null;
  const code = typeof payload?.error?.code === "string" ? payload.error.code : null;
  const requestId =
    typeof payload?.error?.request_id === "string"
      ? payload.error.request_id
      : response.headers.get("X-Request-ID");
  const message =
    messages?.byStatus?.[response.status] ??
    defaultMessages[response.status] ??
    messages?.fallback ??
    "Không thể kết nối tới máy chủ.";
  return new ApiError(
    message,
    response.status,
    retryAfterSeconds(response),
    code,
    requestId,
  );
}

export async function requestJson<T>(
  url: string,
  init: ApiRequestInit = {},
): Promise<T> {
  const {
    timeoutMs = 15_000,
    messages,
    notifyOnUnauthorized = true,
    signal,
    ...requestInit
  } = init;
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(signal?.reason);
  if (signal?.aborted) abortFromCaller();
  else signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = window.setTimeout(
    () => controller.abort(new DOMException("Request timed out", "TimeoutError")),
    timeoutMs,
  );

  try {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...requestInit,
      headers: { Accept: "application/json", ...requestInit.headers },
      signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 401 && notifyOnUnauthorized) notifySessionExpired();
      throw await responseError(response, messages);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    if (controller.signal.aborted) {
      throw new ApiError("Máy chủ phản hồi quá chậm. Vui lòng thử lại.", 0);
    }
    throw new ApiError(messages?.fallback ?? "Không thể kết nối tới máy chủ.", 0);
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}
