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

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  return requestJson(url, {
    ...init,
    messages: {
      fallback: "Không thể xử lý yêu cầu tài liệu.",
      byStatus: {
        403: "Chỉ quản trị viên được quản lý tài liệu.",
        409: "Tài liệu đã thay đổi. Hãy tải lại trước khi thao tác.",
      },
    },
  });
}

export function listDocuments(signal?: AbortSignal): Promise<ManagedDocument[]> {
  return request("/api/v1/documents", { signal });
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
    { method: "POST", headers: { "X-CSRF-Token": csrfToken } },
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
import { requestJson } from "./client";
