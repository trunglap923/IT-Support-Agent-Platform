import { notifySessionExpired, requestJson } from "./client";

export type RunStatus =
  | "queued"
  | "running"
  | "waiting_approval"
  | "resume_queued"
  | "completed"
  | "failed"
  | "cancelled";

export interface RunSnapshot {
  id: string;
  conversation_id: string;
  status: RunStatus;
  outcome: string | null;
  version: number;
  error_code: string | null;
}

export interface RunEventData {
  sequence: number;
  run_id: string;
  type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export type RunConnectionState = "connecting" | "open" | "reconnecting" | "closed";

export class RunStreamError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
  }
}

const terminalStatuses = new Set<RunStatus>(["completed", "failed", "cancelled"]);

function requestError(status: number): RunStreamError {
  if (status === 401) {
    notifySessionExpired();
    return new RunStreamError("Phiên đăng nhập đã hết hạn.", status);
  }
  if (status === 403 || status === 404) {
    return new RunStreamError("Không tìm thấy run hoặc bạn không có quyền xem.", status);
  }
  return new RunStreamError("Không thể tải trạng thái run.", status);
}

export async function getRunSnapshot(
  runId: string,
  signal?: AbortSignal,
  fetchImpl: typeof fetch = fetch,
): Promise<RunSnapshot> {
  const response = await fetchImpl(`/api/v1/runs/${encodeURIComponent(runId)}`, {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw requestError(response.status);
  return (await response.json()) as RunSnapshot;
}

export function cancelRun(
  runId: string,
  expectedVersion: number,
  csrfToken: string,
  reason: "user_requested" | "draft_replaced" = "user_requested",
): Promise<RunSnapshot> {
  return requestJson(`/api/v1/runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ expected_version: expectedVersion, reason }),
    messages: {
      fallback: "Không thể hủy bản nháp hiện tại.",
      byStatus: {
        409: "Bản nháp đã thay đổi hoặc không còn chờ xác nhận.",
      },
    },
  });
}

interface ParsedFrame {
  id?: string;
  event?: string;
  data?: string;
}

export function parseSseFrame(block: string): ParsedFrame {
  const frame: ParsedFrame = {};
  const data: string[] = [];
  for (const line of block.replaceAll("\r\n", "\n").split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const value = separator === -1 ? "" : line.slice(separator + 1).replace(/^ /, "");
    if (field === "id") frame.id = value;
    if (field === "event") frame.event = value;
    if (field === "data") data.push(value);
  }
  if (data.length) frame.data = data.join("\n");
  return frame;
}

async function readEventStream(
  response: Response,
  onEvent: (event: RunEventData) => void,
): Promise<number | null> {
  if (!response.body) throw new RunStreamError("Máy chủ không trả về luồng sự kiện.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastSequence: number | null = null;
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const frame = parseSseFrame(block);
      if (frame.data) {
        const event = JSON.parse(frame.data) as RunEventData;
        if (!Number.isInteger(event.sequence) || event.sequence < 1) {
          throw new RunStreamError("Sự kiện run có sequence không hợp lệ.");
        }
        lastSequence = event.sequence;
        onEvent(event);
      }
      boundary = buffer.indexOf("\n\n");
    }
    if (done) return lastSequence;
  }
}

function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.reject(new DOMException("Aborted", "AbortError"));
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

interface ConsumeRunEventsOptions {
  signal: AbortSignal;
  startingAfter?: number;
  maxReconnectAttempts?: number;
  reconnectDelayMs?: number;
  onEvent: (event: RunEventData) => void;
  onConnectionState?: (state: RunConnectionState) => void;
  fetchImpl?: typeof fetch;
  waitImpl?: (milliseconds: number, signal: AbortSignal) => Promise<void>;
}

export async function consumeRunEvents(
  runId: string,
  options: ConsumeRunEventsOptions,
): Promise<RunSnapshot> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const waitImpl = options.waitImpl ?? wait;
  const maxAttempts = options.maxReconnectAttempts ?? 5;
  let cursor = options.startingAfter ?? 0;
  let reconnectAttempts = 0;

  while (!options.signal.aborted) {
    options.onConnectionState?.(reconnectAttempts ? "reconnecting" : "connecting");
    const headers: Record<string, string> = { Accept: "text/event-stream" };
    if (cursor > 0) headers["Last-Event-ID"] = String(cursor);
    try {
      const response = await fetchImpl(
        `/api/v1/runs/${encodeURIComponent(runId)}/events?after_sequence=${cursor}`,
        { credentials: "same-origin", headers, signal: options.signal },
      );
      if (!response.ok) throw requestError(response.status);
      options.onConnectionState?.("open");
      const receivedSequence = await readEventStream(response, options.onEvent);
      if (receivedSequence !== null) cursor = Math.max(cursor, receivedSequence);
      const snapshot = await getRunSnapshot(runId, options.signal, fetchImpl);
      if (terminalStatuses.has(snapshot.status)) {
        options.onConnectionState?.("closed");
        return snapshot;
      }
    } catch (error) {
      if (options.signal.aborted) throw new DOMException("Aborted", "AbortError");
      if (error instanceof RunStreamError && error.status && error.status < 500) throw error;
    }

    reconnectAttempts += 1;
    if (reconnectAttempts > maxAttempts) {
      throw new RunStreamError("Mất kết nối tới luồng trạng thái run.");
    }
    const delay = Math.min((options.reconnectDelayMs ?? 500) * reconnectAttempts, 4000);
    await waitImpl(delay, options.signal);
  }
  throw new DOMException("Aborted", "AbortError");
}
