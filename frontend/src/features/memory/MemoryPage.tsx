import { useEffect, useState, type FormEvent } from "react";

import {
  confirmMemoryCandidate,
  createMemoryDevice,
  deleteMemoryFact,
  listMemoryCandidates,
  listMemoryDevices,
  listMemoryFacts,
  rejectMemoryCandidate,
  updateMemoryFact,
  type MemoryCandidate,
  type MemoryDevice,
  type MemoryFact,
} from "../../api/memory";
import { EmptyState, LoadingState, PageHeader, StatusBadge } from "../../components/ProductUI";
import { useAuth } from "../auth/useAuth";

export function MemoryPage() {
  const { csrfToken } = useAuth();
  const [devices, setDevices] = useState<MemoryDevice[]>([]);
  const [candidates, setCandidates] = useState<MemoryCandidate[]>([]);
  const [facts, setFacts] = useState<MemoryFact[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh(signal?: AbortSignal) {
    const [nextDevices, nextCandidates, nextFacts] = await Promise.all([
      listMemoryDevices(signal),
      listMemoryCandidates(signal),
      listMemoryFacts(signal),
    ]);
    setDevices(nextDevices);
    setCandidates(nextCandidates);
    setFacts(nextFacts);
  }

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      listMemoryDevices(controller.signal),
      listMemoryCandidates(controller.signal),
      listMemoryFacts(controller.signal),
    ])
      .then(([nextDevices, nextCandidates, nextFacts]) => {
        setDevices(nextDevices);
        setCandidates(nextCandidates);
        setFacts(nextFacts);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải memory.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  async function mutate(action: () => Promise<unknown>, message: string) {
    if (!csrfToken || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      await refresh();
      setNotice(message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật memory.");
    } finally {
      setBusy(false);
    }
  }

  async function addDevice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await mutate(
      () => createMemoryDevice(
        String(data.get("label")),
        String(data.get("platform")) as MemoryDevice["platform"],
        csrfToken ?? "",
      ),
      "Đã thêm thiết bị.",
    );
    form.reset();
  }

  async function confirmCandidate(
    event: FormEvent<HTMLFormElement>,
    candidate: MemoryCandidate,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await mutate(
      () => confirmMemoryCandidate(
        candidate,
        String(data.get("value")),
        candidate.kind === "device" ? String(data.get("device_id")) : null,
        csrfToken ?? "",
      ),
      "Đã xác nhận memory.",
    );
  }

  if (loading) return <LoadingState label="Đang tải memory và thiết bị…" />;
  const deviceNames = new Map(devices.map((device) => [device.id, device.label]));

  return (
    <div className="memory-page">
      <PageHeader
        eyebrow="CONFIRMED MEMORY"
        title="Memory & thiết bị"
        description="Memory luôn hoạt động, nhưng chỉ dữ liệu bạn xác nhận mới được dùng để cá nhân hóa hỗ trợ."
      />
      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="metrics-strip memory-metrics" aria-label="Tổng quan memory">
        <div className="metric"><span>Thiết bị</span><strong>{devices.length}</strong></div>
        <div className="metric"><span>Chờ xác nhận</span><strong>{candidates.length}</strong></div>
        <div className="metric"><span>Fact đã xác nhận</span><strong>{facts.length}</strong></div>
      </section>

      <section className="memory-section">
        <header className="panel-header"><div><h2>Thiết bị của bạn</h2><p>Gắn fact kỹ thuật với đúng máy đang sử dụng.</p></div></header>
        <form className="device-form" onSubmit={(event) => void addDevice(event)}>
          <label>Tên thiết bị<input name="label" placeholder="Laptop công ty" required /></label>
          <label>Hệ điều hành<select name="platform"><option value="windows">Windows</option><option value="macos">macOS</option><option value="linux">Linux</option><option value="other">Khác</option></select></label>
          <button className="primary-button" disabled={busy} type="submit">Thêm thiết bị</button>
        </form>
        {devices.length === 0 ? <EmptyState title="Chưa có thiết bị" description="Thêm laptop hoặc máy trạm để liên kết memory theo thiết bị." /> : (
          <ul className="device-list">{devices.map((device) => <li key={device.id}><span className="device-mark" aria-hidden="true">{device.label.slice(0, 1).toUpperCase()}</span><span>{device.label}<small>{device.platform}</small></span><StatusBadge value={device.active ? "active" : "inactive"} label={device.active ? "Đang dùng" : "Ngừng dùng"} /></li>)}</ul>
        )}
      </section>

      <div className="memory-columns">
        <section className="memory-section">
          <header className="panel-header"><div><h2>Chờ xác nhận</h2><p>Kiểm tra bằng chứng trước khi lưu.</p></div><StatusBadge value="pending" label={String(candidates.length)} /></header>
          {candidates.length === 0 ? <EmptyState title="Không có đề xuất mới" description="Fact được phát hiện từ hội thoại sẽ chờ bạn duyệt tại đây." /> : null}
          <div className="memory-grid">
            {candidates.map((candidate) => (
              <article key={candidate.id}>
                <div className="memory-record-heading"><span>{candidate.kind} · {candidate.key}</span><StatusBadge value="pending" label="Chờ duyệt" /></div>
                <p>{candidate.evidence}</p>
                <form onSubmit={(event) => void confirmCandidate(event, candidate)}>
                  <label>Giá trị<input defaultValue={candidate.value} name="value" required /></label>
                  {candidate.kind === "device" ? <label>Thiết bị<select name="device_id" required><option value="">Chọn thiết bị</option>{devices.map((device) => <option key={device.id} value={device.id}>{device.label}</option>)}</select></label> : null}
                  <div><button className="primary-button" disabled={busy || (candidate.kind === "device" && devices.length === 0)} type="submit">Xác nhận</button><button className="secondary-button" disabled={busy} onClick={() => void mutate(() => rejectMemoryCandidate(candidate, csrfToken ?? ""), "Đã từ chối đề xuất.")} type="button">Từ chối</button></div>
                </form>
              </article>
            ))}
          </div>
        </section>

        <section className="memory-section">
          <header className="panel-header"><div><h2>Đã xác nhận</h2><p>Fact có thể được dùng trong câu trả lời.</p></div><StatusBadge value="active" label={String(facts.length)} /></header>
          {facts.length === 0 ? <EmptyState title="Chưa có memory nào được xác nhận." description="Xác nhận đề xuất để bắt đầu cá nhân hóa hỗ trợ." /> : null}
          <div className="memory-grid">
            {facts.map((fact) => (
              <article key={fact.id}>
                <div className="memory-record-heading"><span>{fact.key} · {fact.scope === "device" ? deviceNames.get(fact.device_id ?? "") ?? "Thiết bị" : "Mọi thiết bị"}</span><StatusBadge value="active" label={fact.scope === "device" ? "Thiết bị" : "Toàn cục"} /></div>
                <form onSubmit={(event) => {
                  event.preventDefault();
                  const value = String(new FormData(event.currentTarget).get("value"));
                  void mutate(() => updateMemoryFact(fact, value, csrfToken ?? ""), "Đã cập nhật memory.");
                }}>
                  <label>Giá trị<input defaultValue={fact.value} name="value" required /></label>
                  <div><button className="secondary-button" disabled={busy} type="submit">Lưu sửa đổi</button><button className="danger-button" disabled={busy} onClick={() => void mutate(() => deleteMemoryFact(fact, csrfToken ?? ""), "Đã xóa memory.")} type="button">Xóa</button></div>
                </form>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
