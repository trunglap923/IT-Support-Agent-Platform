import { useEffect, useState, type FormEvent } from "react";

import {
  listDocuments,
  previewVersion,
  processVersion,
  publishVersion,
  replaceDocumentAcl,
  revokeDocument,
  uploadDocument,
  uploadDocumentVersion,
  type DocumentPreview,
  type ManagedDocument,
} from "../../api/documents";
import { useAuth } from "../auth/useAuth";

function isoNow(): string {
  return new Date().toISOString().slice(0, 16);
}

export function DocumentsPage() {
  const { csrfToken, user } = useAuth();
  const [documents, setDocuments] = useState<ManagedDocument[]>([]);
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [loading, setLoading] = useState(user?.role === "admin");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh(signal?: AbortSignal) {
    const items = await listDocuments(signal);
    setDocuments(items);
  }

  useEffect(() => {
    if (user?.role !== "admin") return;
    const controller = new AbortController();
    void listDocuments(controller.signal)
      .then(setDocuments)
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải tài liệu.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user?.role]);

  if (user?.role !== "admin") {
    return <p className="chat-error" role="alert">Khu vực tài liệu chỉ dành cho quản trị viên.</p>;
  }
  if (loading) return <p>Đang tải tài liệu…</p>;

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
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật tài liệu.");
    } finally {
      setBusy(false);
    }
  }

  async function submitNewDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!csrfToken) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await mutate(async () => {
      const uploaded = await uploadDocument(form, csrfToken);
      setPreview(uploaded);
      formElement.reset();
    }, "Đã tạo document và version draft.");
  }

  async function submitNewVersion(event: FormEvent<HTMLFormElement>, documentId: string) {
    event.preventDefault();
    if (!csrfToken) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    await mutate(async () => {
      const uploaded = await uploadDocumentVersion(documentId, form, csrfToken);
      setPreview(uploaded);
      formElement.reset();
    }, "Đã thêm version draft.");
  }

  return (
    <div className="documents-page">
      <header className="section-heading">
        <p className="eyebrow">KNOWLEDGE GOVERNANCE</p>
        <h1>Quản lý tài liệu</h1>
        <p>Upload tạo draft; chỉ version đã process và publish mới tham gia retrieval.</p>
      </header>
      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <p className="chat-error" role="alert">{error}</p> : null}

      <section className="document-upload-panel">
        <h2>Tạo tài liệu</h2>
        <form onSubmit={(event) => void submitNewDocument(event)}>
          <label>PDF<input accept="application/pdf" name="file" required type="file" /></label>
          <label>Document key<input name="document_key" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" required /></label>
          <label>Tiêu đề<input name="title" required /></label>
          <label>Version<input defaultValue="v1" name="version_label" required /></label>
          <label>Authority<input defaultValue="IT Operations" name="authority" required /></label>
          <label>Ngôn ngữ<input defaultValue="vi" name="language" required /></label>
          <label>Hiệu lực từ<input defaultValue={isoNow()} name="effective_at" required type="datetime-local" /></label>
          <label>Phạm vi<select defaultValue="company" name="visibility"><option value="company">Company</option><option value="it_only">IT only</option></select></label>
          <button className="primary-button" disabled={busy} type="submit">Upload draft</button>
        </form>
      </section>

      <section className="document-grid">
        {documents.length === 0 ? <p>Chưa có tài liệu.</p> : null}
        {documents.map((document) => (
          <article key={document.id}>
            <header>
              <div><small>{document.document_key}</small><h2>{document.title}</h2></div>
              <span>{document.archived ? "revoked" : document.visibility}</span>
            </header>
            <p>Document version {document.version} · access version {document.access_version}</p>
            <label>Phạm vi
              <select
                aria-label={`Phạm vi ${document.document_key}`}
                disabled={busy}
                onChange={(event) => void mutate(
                  () => replaceDocumentAcl(document, event.target.value as "company" | "it_only", null, csrfToken ?? ""),
                  "Đã cập nhật ACL.",
                )}
                value={document.visibility}
              ><option value="company">Company</option><option value="it_only">IT only</option></select>
            </label>
            <div className="document-version-list">
              {document.versions.map((version) => (
                <div key={version.id}>
                  <strong>{version.version_label}</strong><span>{version.status}</span>
                  <button onClick={() => void previewVersion(document.id, version.id).then(setPreview).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Không thể xem preview."))} type="button">Preview</button>
                  {version.status === "draft" || version.status === "failed" ? <button disabled={busy} onClick={() => void mutate(() => processVersion(document.id, version.id, csrfToken ?? ""), "Đã process version; version sẵn sàng publish.")} type="button">Process</button> : null}
                  {version.status === "ready" ? <button disabled={busy} onClick={() => void mutate(() => publishVersion(document, version.id, csrfToken ?? ""), "Đã publish version.")} type="button">Publish</button> : null}
                  {document.current_version_id === version.id ? <button disabled={busy} onClick={() => void mutate(() => revokeDocument(document, csrfToken ?? ""), "Đã revoke tài liệu.")} type="button">Revoke</button> : null}
                </div>
              ))}
            </div>
            <details>
              <summary>Thêm version</summary>
              <form onSubmit={(event) => void submitNewVersion(event, document.id)}>
                <label>PDF<input accept="application/pdf" name="file" required type="file" /></label>
                <label>Version<input name="version_label" required /></label>
                <label>Authority<input defaultValue="IT Operations" name="authority" required /></label>
                <input name="language" type="hidden" value="vi" />
                <input name="effective_at" type="hidden" value={isoNow()} />
                <button disabled={busy} type="submit">Upload version</button>
              </form>
            </details>
          </article>
        ))}
      </section>

      {preview ? (
        <section className="document-preview" aria-label="Preview tài liệu">
          <div><h2>Preview</h2><button onClick={() => setPreview(null)} type="button">Đóng</button></div>
          <p>{preview.pages.length} trang · {preview.byte_size} bytes · {preview.parser_version}</p>
          {preview.pages.map((page) => <article key={page.page_number}><strong>Trang {page.page_number}</strong><p>{page.text}</p></article>)}
        </section>
      ) : null}
    </div>
  );
}
