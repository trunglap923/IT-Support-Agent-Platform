import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { CheckCircle2, Eye, FilePenLine, FileText, MoreHorizontal, Plus, Search, TriangleAlert, X } from "lucide-react";

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
import { AccessDenied, ConfirmDialog, EmptyState, LoadingState, MetricCard, PageHeader, StatusBadge } from "../../components/ProductUI";
import { formatDateTime } from "../../utils/format";
import { useMediaQuery } from "../../hooks/useMediaQuery";

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
  const [selectedDocument, setSelectedDocument] = useState<ManagedDocument | null>(null);
  const compactDrawer = useMediaQuery("(max-width: 900px)");
  const drawer = useRef<HTMLElement>(null);
  const drawerTrigger = useRef<HTMLElement | null>(null);
  const newDocumentTrigger = useRef<HTMLButtonElement>(null);
  const activeDrawer = uploadOpen ? "upload" : selectedDocument ? "detail" : preview ? "preview" : null;

  const closeDrawer = useCallback(() => {
    setUploadOpen(false);
    setSelectedDocument(null);
    setPreview(null);
    const returnTarget = drawerTrigger.current?.isConnected ? drawerTrigger.current : newDocumentTrigger.current;
    requestAnimationFrame(() => returnTarget?.focus());
  }, []);

  async function refresh(signal?: AbortSignal) {
    const page = await listDocumentsPage(null, signal);
    setDocuments(page.items);
    setSelectedDocument((current) => current
      ? page.items.find((document) => document.id === current.id) ?? current
      : null);
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

  useEffect(() => {
    if (!activeDrawer) return;
    const previousOverflow = document.body.style.overflow;
    if (compactDrawer) document.body.style.overflow = "hidden";
    const focusFrame = requestAnimationFrame(() => {
      drawer.current?.querySelector<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), summary, [tabindex]:not([tabindex='-1'])",
      )?.focus();
    });
    const handleDrawerKeyboard = (event: KeyboardEvent) => {
      if (document.querySelector("dialog[open]")) return;
      if (event.key === "Escape") {
        closeDrawer();
        return;
      }
      if (event.key !== "Tab" || !compactDrawer || !drawer.current) return;
      const focusable = [...drawer.current.querySelectorAll<HTMLElement>(
        "a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex='-1'])",
      )].filter((element) => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && (document.activeElement === first || !drawer.current.contains(document.activeElement))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleDrawerKeyboard);
    return () => {
      cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleDrawerKeyboard);
    };
  }, [activeDrawer, closeDrawer, compactDrawer]);

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
    <div className={uploadOpen || preview || selectedDocument ? "documents-page drawer-visible" : "documents-page"}>
      <PageHeader
        eyebrow="KNOWLEDGE GOVERNANCE"
        title="Kho tri thức"
        description="Chỉ version đã xử lý và publish mới được dùng làm nguồn trả lời."
        actions={<button className="primary-button" onClick={(event) => { drawerTrigger.current = event.currentTarget; setSelectedDocument(null); setPreview(null); setUploadOpen(true); }} ref={newDocumentTrigger} type="button"><Plus aria-hidden="true" size={16} /> Tài liệu mới</button>}
      />
      {notice ? <p className="notice-banner" role="status">{notice}</p> : null}
      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="metric-grid" aria-label="Tổng quan tài liệu">
        <MetricCard icon={FileText} label="Tổng tài liệu" value={documents.length} detail="Trong kho tri thức" />
        <MetricCard icon={CheckCircle2} label="Published" value={documents.filter((document) => getDocumentStatus(document) === "published").length} tone="green" detail="Được dùng cho retrieval" />
        <MetricCard icon={FilePenLine} label="Draft" value={documents.filter((document) => getDocumentStatus(document) === "draft").length} tone="amber" detail="Đang chuẩn bị" />
        <MetricCard icon={TriangleAlert} label="Cần rà soát" value={documents.filter((document) => ["failed", "revoked"].includes(getDocumentStatus(document))).length} tone="red" detail="Cần hành động" />
      </section>

      {compactDrawer && activeDrawer ? <button aria-label="Đóng panel tài liệu" className="document-drawer-backdrop" onClick={closeDrawer} type="button" /> : null}

      {uploadOpen ? <section aria-labelledby="document-upload-title" aria-modal={compactDrawer ? true : undefined} className="document-upload-panel document-drawer" ref={drawer} role="dialog">
        <header className="panel-header"><div><h2 id="document-upload-title">Tạo tài liệu mới</h2><p>PDF bắt đầu ở trạng thái draft để kiểm tra trước khi publish.</p></div><button aria-label="Đóng panel tài liệu mới" className="drawer-close" onClick={closeDrawer} type="button"><X aria-hidden="true" size={20} /></button></header>
        <form onSubmit={(event) => void submitNewDocument(event)}>
          <label>PDF<input accept="application/pdf" name="file" required type="file" /><small className="field-hint">Tối đa 10 MB và 100 trang. PDF phải có lớp văn bản; chưa hỗ trợ OCR tài liệu scan.</small></label>
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
          <label className="search-field"><Search aria-hidden="true" size={16} /><span className="sr-only">Tìm tài liệu</span><input onChange={(event) => setQuery(event.target.value)} placeholder="Tìm theo key hoặc tiêu đề…" type="search" value={query} /></label>
          <label><span className="sr-only">Lọc trạng thái tài liệu</span><select aria-label="Lọc trạng thái tài liệu" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="all">Mọi trạng thái</option><option value="draft">Draft</option><option value="ready">Ready</option><option value="published">Published</option><option value="revoked">Revoked</option></select></label>
        </div>
        {filteredDocuments.length === 0 ? (
          <EmptyState title={documents.length === 0 ? "Chưa có tài liệu" : "Không tìm thấy tài liệu"} description={documents.length === 0 ? "Tải PDF đầu tiên để bắt đầu xây dựng kho tri thức." : "Thử thay đổi từ khóa hoặc bộ lọc."} />
        ) : (
          <div className="table-scroll">
            <span className="mobile-scroll-hint">Vuốt ngang để quản lý phiên bản</span>
            <table className="data-table documents-table">
              <thead><tr><th>Tài liệu</th><th>Trạng thái</th><th>Phiên bản</th><th>Phạm vi</th><th>Cập nhật gần nhất</th><th><span className="sr-only">Chi tiết</span></th></tr></thead>
              <tbody>{filteredDocuments.map((document) => (
                <tr key={document.id}>
                  <td><button className="document-title-button" onClick={(event) => { drawerTrigger.current = event.currentTarget; setUploadOpen(false); setPreview(null); setSelectedDocument(document); }} type="button"><span className="document-file-icon"><FileText aria-hidden="true" size={16} /></span><span><strong>{document.title}</strong><small>{document.document_key}</small></span></button></td>
                  <td><StatusBadge value={getDocumentStatus(document)} /></td>
                  <td>{document.versions[0]?.version_label ?? "—"}</td>
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
                  <td>{document.versions[0]?.created_at ? formatDateTime(document.versions[0].created_at) : "—"}</td>
                  <td>
                    <button aria-label={`Mở chi tiết ${document.title}`} className="icon-button" onClick={(event) => { drawerTrigger.current = event.currentTarget; setUploadOpen(false); setPreview(null); setSelectedDocument(document); }} type="button"><MoreHorizontal aria-hidden="true" size={17} /></button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {documentCursor ? <button className="load-more-button" disabled={loadingMore} onClick={() => void loadMoreDocuments()} type="button">{loadingMore ? "Đang tải…" : "Tải thêm tài liệu"}</button> : null}
      </section>

      {selectedDocument ? (
        <aside aria-labelledby="document-detail-title" aria-modal={compactDrawer ? true : undefined} className="document-detail document-drawer" ref={drawer} role="dialog">
          <header className="drawer-header"><div><span className="drawer-document-icon"><FileText aria-hidden="true" /></span><h2 id="document-detail-title">{selectedDocument.title}</h2><p>{selectedDocument.document_key}</p></div><button aria-label="Đóng chi tiết tài liệu" className="icon-button" onClick={closeDrawer} type="button"><X aria-hidden="true" size={19} /></button></header>
          <div className="document-detail-summary"><StatusBadge value={getDocumentStatus(selectedDocument)} /><span>{selectedDocument.versions.length} phiên bản</span><span>{selectedDocument.visibility}</span></div>
          <dl className="detail-list">
            <div><dt>Phạm vi</dt><dd>{selectedDocument.visibility}</dd></div>
            <div><dt>Document version</dt><dd>{selectedDocument.version}</dd></div>
            <div><dt>Access version</dt><dd>{selectedDocument.access_version}</dd></div>
          </dl>
          <section className="drawer-section"><h3>Lịch sử phiên bản</h3><div className="document-version-list">{selectedDocument.versions.map((version) => (
            <div key={version.id}><span><strong>{version.version_label}</strong><small>{formatDateTime(version.created_at)}</small></span><StatusBadge value={version.status} /><button onClick={() => void previewVersion(selectedDocument.id, version.id).then((nextPreview) => { setSelectedDocument(null); setPreview(nextPreview); }).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "Không thể xem preview."))} type="button"><Eye aria-hidden="true" size={14} /> Xem</button>{version.status === "draft" || version.status === "failed" ? <button disabled={busy} onClick={() => void mutate(() => processVersion(selectedDocument.id, version.id, csrfToken ?? ""), "Đã process version; version sẵn sàng publish.")} type="button">Process</button> : null}{version.status === "ready" ? <button disabled={busy} onClick={() => void mutate(() => publishVersion(selectedDocument, version.id, csrfToken ?? ""), "Đã publish version.")} type="button">Publish</button> : null}{selectedDocument.current_version_id === version.id ? <button className="danger-button" disabled={busy} onClick={() => setDocumentToRevoke(selectedDocument)} type="button">Revoke</button> : null}</div>
          ))}</div></section>
          <details className="new-version-form drawer-section"><summary><Plus aria-hidden="true" size={15} /> Thêm phiên bản</summary><form onSubmit={(event) => void submitNewVersion(event, selectedDocument.id)}><label>PDF<input accept="application/pdf" name="file" required type="file" /><small className="field-hint">Tối đa 10 MB và 100 trang. PDF phải có lớp văn bản; chưa hỗ trợ OCR tài liệu scan.</small></label><label>Version<input name="version_label" required /></label><label>Authority<input defaultValue="IT Operations" name="authority" required /></label><input name="language" type="hidden" value="vi" /><input name="effective_at" type="hidden" value={isoNow()} /><button className="primary-button" disabled={busy} type="submit">Upload version</button></form></details>
        </aside>
      ) : null}

      {preview ? (
        <aside aria-labelledby="document-preview-title" aria-modal={compactDrawer ? true : undefined} className="document-preview document-drawer" ref={drawer} role="dialog">
          <div><div><p className="eyebrow">DOCUMENT PREVIEW</p><h2 id="document-preview-title">Preview</h2></div><button aria-label="Đóng preview" className="icon-button" onClick={closeDrawer} type="button"><X aria-hidden="true" size={19} /></button></div>
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
