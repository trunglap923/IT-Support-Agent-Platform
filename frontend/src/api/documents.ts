export type DocumentVisibility = "company" | "department" | "it_only";

export interface DocumentVersion {
  id: string;
  version_label: string;
  status: "draft" | "processing" | "ready" | "published" | "superseded" | "failed";
  authority: string;
  language: string;
  effective_at: string;
  expires_at: string | null;
  created_at: string;
}

export interface ManagedDocument {
  id: string;
  document_key: string;
  title: string;
  visibility: DocumentVisibility;
  department_id: string | null;
  archived: boolean;
  current_version_id: string | null;
  access_version: number;
  version: number;
  granted_department_ids: string[];
  versions: DocumentVersion[];
}

export interface PreviewPage {
  page_number: number;
  text: string;
}

export interface DocumentPreview {
  document_id: string;
  version_id: string;
  document_key?: string;
  title?: string;
  version_label?: string;
  status?: string;
  job_id?: string;
  byte_size: number;
  parser_version: string;
  pages: PreviewPage[];
}

async function request<T>(url: string, init?: ApiRequestInit): Promise<T> {
  return requestJson(url, {
    ...init,
    messages: {
      fallback: "Không thể xử lý yêu cầu tài liệu.",
      byCode: {
        PDF_NO_TEXT: "PDF không có văn bản có thể trích xuất. Hệ thống chưa hỗ trợ OCR cho PDF scan.",
        PDF_TOO_MANY_PAGES: "PDF vượt quá giới hạn 100 trang.",
        PDF_TOO_LARGE: "PDF vượt quá giới hạn 10 MB.",
        PDF_TEXT_TOO_LARGE: "Nội dung văn bản trích xuất từ PDF vượt quá giới hạn cho phép.",
        PDF_ENCRYPTED: "PDF đang được bảo vệ bằng mật khẩu hoặc mã hóa.",
        PDF_MALFORMED: "Cấu trúc PDF bị lỗi hoặc không thể đọc.",
        PDF_INVALID_SIGNATURE: "Tệp tải lên không có định dạng PDF hợp lệ.",
        PDF_PARSE_TIMEOUT: "PDF mất quá nhiều thời gian để xử lý.",
        PDF_RESOURCE_LIMIT: "PDF cần quá nhiều tài nguyên để xử lý.",
        PDF_WORKER_FAILED: "Bộ đọc PDF gặp lỗi khi trích xuất nội dung.",
        EMPTY_UPLOAD: "Tệp PDF tải lên đang trống.",
        INGESTION_FAILED: "Không thể xử lý tài liệu. Hãy kiểm tra kết nối embedding hoặc xem trạng thái ingestion.",
        INVALID_METADATA: "Thông tin tài liệu không hợp lệ. Hãy kiểm tra document key, phiên bản và ngày hiệu lực.",
        VALIDATION_ERROR: "Thông tin upload không hợp lệ. Hãy kiểm tra các trường bắt buộc.",
      },
      byStatus: {
        403: "Chỉ quản trị viên được quản lý tài liệu.",
        409: "Tài liệu đã thay đổi. Hãy tải lại trước khi thao tác.",
      },
    },
  });
}

export function listDocumentsPage(
  cursor: string | null = null,
  signal?: AbortSignal,
): Promise<CursorPage<ManagedDocument>> {
  return request(paginatedUrl("/api/v1/documents", {}, cursor), { signal });
}

export async function listDocuments(signal?: AbortSignal): Promise<ManagedDocument[]> {
  return (await listDocumentsPage(null, signal)).items;
}

export function uploadDocument(form: FormData, csrfToken: string): Promise<DocumentPreview> {
  return request("/api/v1/documents/uploads", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: form,
  });
}

export function uploadDocumentVersion(
  documentId: string,
  form: FormData,
  csrfToken: string,
): Promise<DocumentPreview> {
  return request(`/api/v1/documents/${encodeURIComponent(documentId)}/versions`, {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: form,
  });
}

export function previewVersion(
  documentId: string,
  versionId: string,
): Promise<DocumentPreview> {
  return request(
    `/api/v1/documents/${encodeURIComponent(documentId)}/versions/${encodeURIComponent(versionId)}/preview`,
  );
}

export function processVersion(
  documentId: string,
  versionId: string,
  csrfToken: string,
): Promise<{ status: string }> {
  return request(
    `/api/v1/documents/${encodeURIComponent(documentId)}/versions/${encodeURIComponent(versionId)}/process`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      timeoutMs: 120_000,
    },
  );
}

export function publishVersion(
  document: ManagedDocument,
  versionId: string,
  csrfToken: string,
): Promise<ManagedDocument> {
  return request(`/api/v1/documents/${encodeURIComponent(document.id)}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ version_id: versionId, expected_version: document.version }),
  });
}

export function revokeDocument(
  document: ManagedDocument,
  csrfToken: string,
): Promise<ManagedDocument> {
  return request(`/api/v1/documents/${encodeURIComponent(document.id)}/revoke`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ expected_version: document.version }),
  });
}

export function replaceDocumentAcl(
  document: ManagedDocument,
  visibility: DocumentVisibility,
  departmentId: string | null,
  csrfToken: string,
): Promise<ManagedDocument> {
  return request(`/api/v1/documents/${encodeURIComponent(document.id)}/acl`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    body: JSON.stringify({
      expected_version: document.version,
      visibility,
      department_id: visibility === "department" ? departmentId : null,
      granted_department_ids: [],
    }),
  });
}
import { requestJson, type ApiRequestInit } from "./client";
import type { CursorPage } from "./pagination";
import { paginatedUrl } from "./pagination";
