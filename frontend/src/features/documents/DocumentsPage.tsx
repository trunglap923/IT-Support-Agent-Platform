import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import {
  listDocumentsPage,
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
import { AccessDenied, ConfirmDialog, EmptyState, LoadingState, PageHeader, StatusBadge } from "../../components/ProductUI";

function isoNow(): string {
  return new Date().toISOString().slice(0, 16);
}

function getDocumentStatus(document: ManagedDocument): string {
  if (document.archived) return "revoked";
  const current = document.versions.find((version) => version.id === document.current_version_id);
  return current?.status ?? document.versions[0]?.status ?? "draft";
}

export function DocumentsPage() {
  const { csrfToken, user } = useAuth();
  const [documents, setDocuments] = useState<ManagedDocument[]>([]);
  const [preview, setPreview] = useState<DocumentPreview | null>(null);
  const [loading, setLoading] = useState(user?.role === "admin");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [documentCursor, setDocumentCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [documentToRevoke, setDocumentToRevoke] = useState<ManagedDocument | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const uploadPanel = useRef<HTMLElement>(null);

  async function refresh(signal?: AbortSignal) {
    const page = await listDocumentsPage(null, signal);
    setDocuments(page.items);
    setDocumentCursor(page.next_cursor);
  }

  useEffect(() => {
    if (user?.role !== "admin") return;
    const controller = new AbortController();
    void listDocumentsPage(null, controller.signal)
      .then((page) => {
        setDocuments(page.items);
        setDocumentCursor(page.next_cursor);
      })
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải tài liệu.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [user?.role]);

  const filteredDocuments = useMemo(() => documents.filter((document) => {
    const matchesQuery = `${document.document_key} ${document.title}`
      .toLowerCase()
      .includes(query.toLowerCase());
    return matchesQuery && (statusFilter === "all" || getDocumentStatus(document) === statusFilter);
  }), [documents, query, statusFilter]);

  if (user?.role !== "admin") {
    return <AccessDenied message="Khu vực tài liệu chỉ dành cho quản trị viên." />;
  }
  if (loading) return <LoadingState label="Đang tải kho tri thức…" />;

  async function mutate(action: () => Promise<unknown>, message: string): Promise<boolean> {
    if (!csrfToken || busy) return false;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      await refresh();
      setNotice(message);
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể cập nhật tài liệu.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function loadMoreDocuments() {
    if (!documentCursor || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    try {
      const page = await listDocumentsPage(documentCursor);
      setDocuments((current) => [...current, ...page.items]);
      setDocumentCursor(page.next_cursor);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Không thể tải thêm tài liệu.");
    } finally {
      setLoadingMore(false);
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
      setUploadOpen(false);
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
    <div className={uploadOpen || preview ? "documents-page drawer-visible" : "documents-page"}>
      <PageHeader
        eyebrow="KNOWLEDGE GOVERNANCE"
        title="Kho tri thức"
        description="Chỉ version đã xử lý và publish mới được dùng làm nguồn trả lời."
        actions={<button className="primary-button" onClick={() => { setPreview(null); setUploadOpen(true); }} type="button">+ Tài liệu mới</button>}
      />
      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="document-summary" aria-label="Tổng quan tài liệu">
        <div><span className="metric-icon">▤</span><span><small>Tổng tài liệu</small><strong>{documents.length}</strong></span></div>
        <div><span className="metric-icon green">✓</span><span><small>Published</small><strong>{documents.filter((document) => getDocumentStatus(document) === "published").length}</strong></span></div>
        <div><span className="metric-icon amber">▧</span><span><small>Draft</small><strong>{documents.filter((document) => getDocumentStatus(document) === "draft").length}</strong></span></div>
        <div><span className="metric-icon red">△</span><span><small>Cần rà soát</small><strong>{documents.filter((document) => ["failed", "revoked"].includes(getDocumentStatus(document))).length}</strong></span></div>
      </section>

      {uploadOpen ? <section className="document-upload-panel document-drawer" ref={uploadPanel}>
        <header className="panel-header"><div><h2>Tạo tài liệu mới</h2><p>PDF bắt đầu ở trạng thái draft để kiểm tra trước khi publish.</p></div><button aria-label="Đóng panel tài liệu mới" className="drawer-close" onClick={() => setUploadOpen(false)} type="button">×</button></header>
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
      </section> : null}

      <section className="panel document-library">
        <header className="panel-header"><div><h2>Kho tài liệu</h2><p>{documents.length} tài liệu được quản lý</p></div></header>
        <div className="filter-bar">
          <label className="search-field"><span className="sr-only">Tìm tài liệu</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo key hoặc tiêu đề…" type="search" value={query} /></label>
          <label><span className="sr-only">Lọc trạng thái tài liệu</span><select aria-label="Lọc trạng thái tài liệu" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="all">Mọi trạng thái</option><option value="draft">Draft</option><option value="ready">Ready</option><option value="published">Published</option><option value="revoked">Revoked</option></select></label>
        </div>
        {filteredDocuments.length === 0 ? (
          <EmptyState title={documents.length === 0 ? "Chưa có tài liệu" : "Không tìm thấy tài liệu"} description={documents.length === 0 ? "Tải PDF đầu tiên để bắt đầu xây dựng kho tri thức." : "Thử thay đổi từ khóa hoặc bộ lọc."} />
        ) : (
          <div className="table-scroll">
            <span className="mobile-scroll-hint">Vuốt ngang để quản lý version →</span>
            <table className="data-table documents-table">
              <thead><tr><th>Tài liệu</th><th>Trạng thái</th><th>Phạm vi</th><th>Versions</th><th>Quản lý</th></tr></thead>
              <tbody>{filteredDocuments.map((document) => (
                <tr key={document.id}>
                  <td><small>{document.document_key}</small><h3>{document.title}</h3><small>Document v{document.version} · Access v{document.access_version}</small></td>
                  <td><StatusBadge value={getDocumentStatus(document)} /></td>
                  <td>
                    <label>
                      <span className="sr-only">Phạm vi</span>
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
                  </td>
                  <td>{document.versions.length}</td>
                  <td>
                    <details className="document-manage">
                      <summary>Quản lý</summary>
                      <div className="document-manage-panel">
                        <div className="document-version-list">
                          {document.versions.map((version) => (
                            <div key={version.id}>
                              <strong>{version.version_label}</strong><StatusBadge value={version.status} />
                              <button onClick={() => void previewVersion(document.id, version.id).then((nextPreview) => { setUploadOpen(false); setPreview(nextPreview); }).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Không thể xem preview."))} type="button">Preview</button>
                              {version.status === "draft" || version.status === "failed" ? <button disabled={busy} onClick={() => void mutate(() => processVersion(document.id, version.id, csrfToken ?? ""), "Đã process version; version sẵn sàng publish.")} type="button">Process</button> : null}
                              {version.status === "ready" ? <button disabled={busy} onClick={() => void mutate(() => publishVersion(document, version.id, csrfToken ?? ""), "Đã publish version.")} type="button">Publish</button> : null}
                              {document.current_version_id === version.id ? <button className="danger-button" disabled={busy} onClick={() => setDocumentToRevoke(document)} type="button">Revoke</button> : null}
                            </div>
                          ))}
                        </div>
                        <details className="new-version-form">
                          <summary>+ Thêm version</summary>
                          <form onSubmit={(event) => void submitNewVersion(event, document.id)}>
                            <label>PDF<input accept="application/pdf" name="file" required type="file" /></label>
                            <label>Version<input name="version_label" required /></label>
                            <label>Authority<input defaultValue="IT Operations" name="authority" required /></label>
                            <input name="language" type="hidden" value="vi" />
                            <input name="effective_at" type="hidden" value={isoNow()} />
                            <button disabled={busy} type="submit">Upload version</button>
                          </form>
                        </details>
                      </div>
                    </details>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {documentCursor ? <button className="load-more-button" disabled={loadingMore} onClick={() => void loadMoreDocuments()} type="button">{loadingMore ? "Đang tải…" : "Tải thêm tài liệu"}</button> : null}
      </section>

      {preview ? (
        <aside className="document-preview document-drawer" aria-label="Preview tài liệu">
          <div><div><p className="eyebrow">DOCUMENT PREVIEW</p><h2>Preview</h2></div><button onClick={() => setPreview(null)} type="button">Đóng</button></div>
          <p>{preview.pages.length} trang · {preview.byte_size} bytes · {preview.parser_version}</p>
          <div className="preview-pages">{preview.pages.map((page) => <article key={page.page_number}><strong>Trang {page.page_number}</strong><p>{page.text}</p></article>)}</div>
        </aside>
      ) : null}
      <ConfirmDialog
        busy={busy}
        confirmLabel="Revoke tài liệu"
        description="Version hiện hành sẽ ngừng được dùng cho retrieval và citation mới."
        onCancel={() => setDocumentToRevoke(null)}
        onConfirm={() => {
          if (!documentToRevoke) return;
          void mutate(
            () => revokeDocument(documentToRevoke, csrfToken ?? ""),
            "Đã revoke tài liệu.",
          ).then((succeeded) => {
            if (succeeded) setDocumentToRevoke(null);
          });
        }}
        open={documentToRevoke !== null}
        title="Revoke tài liệu hiện hành?"
        tone="danger"
      />
    </div>
  );
}
