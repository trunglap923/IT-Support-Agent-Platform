import { useEffect, useMemo, useRef, useState } from "react";

import type { RunEventData, RunStatus } from "../../api/run-events";
import { useRunEvents } from "./useRunEvents";

type ProgressState = "complete" | "running" | "pending" | "warning" | "waiting";

export interface ProgressStep {
  id: string;
  title: string;
  detail?: string;
  state: ProgressState;
}

export interface RunProgressSummary {
  runId: string;
  status: RunStatus;
  durationSeconds: number | null;
  steps: ProgressStep[];
}

const stageTitles: Record<string, string> = {
  analyze: "Phân tích yêu cầu",
  device: "Kiểm tra thông tin thiết bị",
  knowledge: "Tìm kiếm kho tri thức",
  service: "Kiểm tra trạng thái dịch vụ",
  support_data: "Kiểm tra thông tin ticket",
  approval: "Chờ bạn xác nhận",
  answer: "Tổng hợp hướng xử lý",
};

const stageOrder = ["analyze", "device", "knowledge", "service", "support_data", "approval", "answer"];
function progressSteps(events: RunEventData[], status: RunStatus | undefined): ProgressStep[] {
  const byStage = new Map<string, { status: string; detail?: string; count?: number }>();
  for (const event of events) {
    if (event.type !== "agent.progress") continue;
    const stage = event.payload.stage;
    const eventStatus = event.payload.status;
    if (typeof stage !== "string" || !stageTitles[stage] || typeof eventStatus !== "string") continue;
    byStage.set(stage, {
      status: eventStatus,
      detail: typeof event.payload.detail === "string" ? event.payload.detail : undefined,
      count: typeof event.payload.count === "number" ? event.payload.count : undefined,
    });
  }

  const included = new Set(["analyze", "device", "answer", ...byStage.keys()]);
  const ordered = stageOrder.filter((stage) => included.has(stage));
  let activeFound = false;
  return ordered.map((id) => {
    const item = byStage.get(id);
    let state: ProgressState = "pending";
    if (item?.status === "completed") state = "complete";
    else if (item?.status === "warning") state = "warning";
    else if (item?.status === "waiting_approval") state = "waiting";
    else if (item?.status === "started" || item?.status === "running") {
      state = "running";
      activeFound = true;
    } else if (!activeFound && status === "running" && id === "analyze") {
      state = "running";
      activeFound = true;
    }
    if (status === "failed" && state === "running") state = "warning";
    if (status === "cancelled" && state === "running") state = "warning";
    return {
      id,
      title: stageTitles[id],
      detail: item?.detail,
      state,
    };
  });
}

function runStartedAt(events: RunEventData[]): number | null {
  const started = events.find((event) => event.type === "run.running");
  const timestamp = started ? new Date(started.timestamp).getTime() : Number.NaN;
  return Number.isFinite(timestamp) ? timestamp : null;
}

function runDuration(events: RunEventData[]): number | null {
  const start = runStartedAt(events);
  const terminal = [...events].reverse().find((event) =>
    ["run.completed", "run.failed", "run.cancelled"].includes(event.type),
  );
  if (start === null || !terminal) return null;
  const end = new Date(terminal.timestamp).getTime();
  return Number.isFinite(end) ? Math.max(0, Math.round((end - start) / 1_000)) : null;
}

function stateLabel(state: ProgressState): string {
  if (state === "complete") return "Hoàn tất";
  if (state === "running") return "Đang thực hiện";
  if (state === "warning") return "Cần lưu ý";
  if (state === "waiting") return "Chờ xác nhận";
  return "Đang chờ";
}

function stateIcon(state: ProgressState): string {
  if (state === "complete") return "✓";
  if (state === "running") return "";
  if (state === "warning") return "!";
  if (state === "waiting") return "…";
  return "";
}

function currentStep(steps: ProgressStep[]): ProgressStep | undefined {
  return steps.find((step) => step.state === "running" || step.state === "waiting")
    ?? [...steps].reverse().find((step) => step.state === "complete" || step.state === "warning");
}

export function RunProgressDetails({ steps }: { steps: ProgressStep[] }) {
  return (
    <ol className="run-progress-steps">
      {steps.map((step) => (
        <li className={`run-progress-step ${step.state}`} key={step.id}>
          <span className="progress-step-icon" aria-hidden="true">{stateIcon(step.state)}</span>
          <span className="progress-step-copy">
            <strong>{step.title}</strong>
            {step.detail ? <small>{step.detail}</small> : null}
          </span>
          <span className="sr-only">{stateLabel(step.state)}</span>
        </li>
      ))}
    </ol>
  );
}

export function CompletedRunProgress({ summary }: { summary: RunProgressSummary }) {
  const [expanded, setExpanded] = useState(false);
  const completedCount = summary.steps.filter((step) => step.state === "complete").length;
  const duration = summary.durationSeconds === null ? "" : ` · ${summary.durationSeconds} giây`;
  return (
    <section className="completed-run-progress" aria-label="Tóm tắt quá trình xử lý">
      <div className="completed-progress-heading">
        <span className="completed-progress-check" aria-hidden="true">✓</span>
        <span>Đã hoàn tất{duration}</span>
        <button aria-expanded={expanded} onClick={() => setExpanded((value) => !value)} type="button">
          {expanded ? "Thu gọn" : `Đã kiểm tra ${completedCount} bước`}
        </button>
      </div>
      {expanded ? <RunProgressDetails steps={summary.steps} /> : null}
    </section>
  );
}

export function RunStatusPanel({
  runId,
  onTerminal,
  onStatus,
  onStreamText,
  onProgressComplete,
}: {
  runId: string;
  onTerminal?: (status: string) => void;
  onStatus?: (status: string) => void;
  onStreamText?: (text: string) => void;
  onProgressComplete?: (summary: RunProgressSummary) => void;
}) {
  const { snapshot, events, streamedText, connectionState, error, retry } = useRunEvents(runId);
  const [expanded, setExpanded] = useState(false);
  const notifiedStatus = useRef<string | null>(null);
  const notifiedSummary = useRef<string | null>(null);
  const steps = useMemo(() => progressSteps(events, snapshot?.status), [events, snapshot?.status]);
  const active = currentStep(steps);
  const consideredSteps = steps.filter((step) => step.state !== "pending").length;
  const completedSteps = steps.filter((step) => step.state === "complete").length;
  const terminal = snapshot && ["completed", "failed", "cancelled"].includes(snapshot.status);

  useEffect(() => {
    if (!snapshot) return;
    const notificationKey = `${runId}:${snapshot.status}`;
    if (notifiedStatus.current === notificationKey) return;
    notifiedStatus.current = notificationKey;
    onStatus?.(snapshot.status);
    if (["completed", "failed", "cancelled"].includes(snapshot.status)) {
      const summaryKey = `${runId}:summary`;
      if (notifiedSummary.current !== summaryKey) {
        notifiedSummary.current = summaryKey;
        onProgressComplete?.({
          runId,
          status: snapshot.status,
          durationSeconds: runDuration(events),
          steps: progressSteps(events, snapshot.status),
        });
      }
      onTerminal?.(snapshot.status);
    }
  }, [events, onProgressComplete, onStatus, onTerminal, runId, snapshot]);

  useEffect(() => {
    onStreamText?.(streamedText ?? "");
  }, [onStreamText, streamedText]);

  const title = snapshot?.status === "waiting_approval"
    ? "Đang chờ bạn xác nhận"
    : snapshot?.status === "queued" || snapshot?.status === "resume_queued"
      ? "Đang chuẩn bị xử lý yêu cầu…"
      : snapshot?.status === "failed"
        ? "Agent chưa thể hoàn tất yêu cầu"
        : snapshot?.status === "cancelled"
          ? "Đã dừng xử lý"
          : "Đang xử lý yêu cầu của bạn…";

  return (
    <section className={`run-monitor${terminal ? " terminal" : ""}`} aria-live="polite">
      <div className="run-monitor-heading">
        <span className="run-agent-mark" aria-hidden="true">✣</span>
        <div className="run-monitor-copy">
          <h2>{title}</h2>
          <p>{active?.title ?? (snapshot?.status === "waiting_approval" ? "Không có thao tác nào được thực hiện trước khi bạn xác nhận." : "Đang cập nhật tiến trình an toàn của Agent.")}</p>
        </div>
        <span className="run-progress-count">{completedSteps}/{Math.max(consideredSteps, steps.length)} bước</span>
      </div>
      <div className="run-progress-track" role="progressbar" aria-label="Tiến độ xử lý" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={completedSteps}>
        <span style={{ width: `${steps.length ? (completedSteps / steps.length) * 100 : 0}%` }} />
      </div>
      <div className="run-progress-summary">
        {active?.detail ? <p>{active.detail}</p> : <p>{active?.state === "waiting" ? "Đang đợi bạn duyệt thao tác." : "Agent đang thực hiện các bước hỗ trợ."}</p>}
        <button aria-expanded={expanded} onClick={() => setExpanded((value) => !value)} type="button">
          {expanded ? "Thu gọn" : "Xem chi tiết"}
        </button>
      </div>
      {expanded ? <RunProgressDetails steps={steps} /> : null}
      {error ? (
        <div className="run-error" role="alert">
          <p>{error}</p>
          <button onClick={retry} type="button">Thử kết nối lại</button>
        </div>
      ) : connectionState === "reconnecting" ? (
        <p className="run-connection-note" role="status">Đang nối lại cập nhật tiến trình…</p>
      ) : null}
    </section>
  );
}
