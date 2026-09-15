import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { RunStatusPanel } from "./chat/RunStatusPanel";

export function ChatPlaceholderPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runId = searchParams.get("run_id");
  const [draftRunId, setDraftRunId] = useState(runId ?? "");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = draftRunId.trim();
    setSearchParams(normalized ? { run_id: normalized } : {});
  }

  return (
    <div className="run-monitor-page">
      <section className="placeholder-card">
        <p className="eyebrow">WP-03 · EVENT STREAM</p>
        <h1>Theo dõi run</h1>
        <p>
          Nhập run ID để xem trạng thái đã lưu và các event mới qua SSE. Composer,
          câu trả lời và citation sẽ được nối trong WP-06.
        </p>
        <form className="run-id-form" onSubmit={handleSubmit}>
          <label htmlFor="run-id">Run ID</label>
          <div>
            <input
              id="run-id"
              onChange={(event) => setDraftRunId(event.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              required
              type="text"
              value={draftRunId}
            />
            <button type="submit">Theo dõi</button>
          </div>
        </form>
      </section>
      {runId ? <RunStatusPanel key={runId} runId={runId} /> : null}
    </div>
  );
}
