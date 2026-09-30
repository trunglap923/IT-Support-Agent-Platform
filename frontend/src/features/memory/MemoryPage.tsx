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

  if (loading) return <p>Đang tải memory…</p>;
  const deviceNames = new Map(devices.map((device) => [device.id, device.label]));

  return (
    <div className="memory-page">
      <header className="section-heading">
        <p className="eyebrow">CONFIRMED MEMORY</p>
        <h1>Memory của bạn</h1>
        <p>Memory luôn hoạt động, nhưng chỉ dữ liệu bạn xác nhận mới được dùng. Bạn có thể sửa hoặc xóa từng mục bất cứ lúc nào.</p>
      </header>
      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <p className="chat-error" role="alert">{error}</p> : null}

      <section className="memory-section">
        <h2>Thiết bị</h2>
        <form className="device-form" onSubmit={(event) => void addDevice(event)}>
          <label>Tên thiết bị<input name="label" placeholder="Laptop công ty" required /></label>
          <label>Hệ điều hành<select name="platform"><option value="windows">Windows</option><option value="macos">macOS</option><option value="linux">Linux</option><option value="other">Khác</option></select></label>
          <button className="primary-button" disabled={busy} type="submit">Thêm thiết bị</button>
        </form>
        <ul className="device-list">{devices.map((device) => <li key={device.id}>{device.label}<small>{device.platform}</small></li>)}</ul>
      </section>

      <section className="memory-section">
        <h2>Đề xuất chờ xác nhận</h2>
        {candidates.length === 0 ? <p>Không có đề xuất mới.</p> : null}
        <div className="memory-grid">
          {candidates.map((candidate) => (
            <article key={candidate.id}>
              <span>{candidate.kind} · {candidate.key}</span>
              <p>{candidate.evidence}</p>
              <form onSubmit={(event) => void confirmCandidate(event, candidate)}>
                <label>Giá trị<input defaultValue={candidate.value} name="value" required /></label>
                {candidate.kind === "device" ? <label>Thiết bị<select name="device_id" required><option value="">Chọn thiết bị</option>{devices.map((device) => <option key={device.id} value={device.id}>{device.label}</option>)}</select></label> : null}
                <div><button className="primary-button" disabled={busy || (candidate.kind === "device" && devices.length === 0)} type="submit">Xác nhận</button><button disabled={busy} onClick={() => void mutate(() => rejectMemoryCandidate(candidate, csrfToken ?? ""), "Đã từ chối đề xuất.")} type="button">Từ chối</button></div>
              </form>
            </article>
          ))}
        </div>
      </section>

      <section className="memory-section">
        <h2>Memory đã xác nhận</h2>
        {facts.length === 0 ? <p>Chưa có memory nào được xác nhận.</p> : null}
        <div className="memory-grid">
          {facts.map((fact) => (
            <article key={fact.id}>
              <span>{fact.key} · {fact.scope === "device" ? deviceNames.get(fact.device_id ?? "") ?? "Thiết bị" : "Mọi thiết bị"}</span>
              <form onSubmit={(event) => {
                event.preventDefault();
                const value = String(new FormData(event.currentTarget).get("value"));
                void mutate(() => updateMemoryFact(fact, value, csrfToken ?? ""), "Đã cập nhật memory.");
              }}>
                <label>Giá trị<input defaultValue={fact.value} name="value" required /></label>
                <div><button disabled={busy} type="submit">Lưu sửa đổi</button><button className="danger-button" disabled={busy} onClick={() => void mutate(() => deleteMemoryFact(fact, csrfToken ?? ""), "Đã xóa memory.")} type="button">Xóa</button></div>
              </form>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
