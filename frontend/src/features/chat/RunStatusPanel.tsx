import { useRunEvents } from "./useRunEvents";

const statusLabels: Record<string, string> = {
  queued: "Đang chờ worker",
  running: "Đang xử lý",
  waiting_approval: "Chờ xác nhận",
  resume_queued: "Đang chờ tiếp tục",
  completed: "Hoàn thành",
  failed: "Thất bại",
  cancelled: "Đã hủy",
};

export function RunStatusPanel({ runId }: { runId: string }) {
  const { snapshot, events, connectionState, error, retry } = useRunEvents(runId);

  return (
    <section className="run-monitor" aria-live="polite">
      <div className="run-monitor-heading">
        <div>
          <p className="panel-label">RUN STATUS</p>
          <h2>{snapshot ? statusLabels[snapshot.status] : "Đang tải trạng thái…"}</h2>
        </div>
        <span className={`connection-state ${connectionState}`}>{connectionState}</span>
      </div>
      <code>{runId}</code>
      {error ? (
        <div className="run-error" role="alert">
          <p>{error}</p>
          <button onClick={retry} type="button">
            Thử kết nối lại
          </button>
        </div>
      ) : null}
      {events.length ? (
        <ol className="run-events">
          {events.map((event) => (
            <li key={event.sequence}>
              <span>#{event.sequence}</span>
              <strong>{event.type}</strong>
              <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleTimeString("vi-VN")}</time>
            </li>
          ))}
        </ol>
      ) : (
        <p className="empty-events">Chưa có event mới trong kết nối này.</p>
      )}
    </section>
  );
}
