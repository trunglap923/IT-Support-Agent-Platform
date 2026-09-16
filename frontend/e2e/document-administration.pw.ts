import { expect, test, type Page, type Route } from "@playwright/test";

const admin = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  email: "admin@example.com",
  display_name: "Document Admin",
  role: "admin",
  department_id: "22222222-2222-2222-2222-222222222222",
  department_key: "engineering",
};
const employee = { ...admin, email: "employee@example.com", role: "employee" };

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockSession(page: Page, user = admin) {
  await page.route("**/api/v1/auth/me", (route) =>
    json(route, { user, csrf_token: "csrf-documents-e2e" }),
  );
}

test("admin uploads, previews, processes, publishes and revokes a document", async ({ page }) => {
  await mockSession(page);
  let documentExists = false;
  let versionStatus = "draft";
  let documentVersion = 1;
  let currentVersionId: string | null = null;
  let archived = false;
  const documentId = "10000000-0000-0000-0000-000000000001";
  const versionId = "20000000-0000-0000-0000-000000000001";

  const responseDocument = () => ({
    id: documentId,
    document_key: "vpn-admin-guide",
    title: "VPN admin guide",
    visibility: "company",
    department_id: null,
    archived,
    current_version_id: currentVersionId,
    access_version: archived ? 2 : 1,
    version: documentVersion,
    granted_department_ids: [],
    versions: [{ id: versionId, version_label: "v1", status: versionStatus, authority: "IT Operations", language: "vi", effective_at: "2026-09-16T00:00:00Z", expires_at: null, created_at: "2026-09-16T00:00:00Z" }],
  });

  await page.route("**/api/v1/documents", (route) =>
    json(route, documentExists ? [responseDocument()] : []),
  );
  await page.route("**/api/v1/documents/uploads", async (route) => {
    expect(route.request().headers()["x-csrf-token"]).toBe("csrf-documents-e2e");
    documentExists = true;
    await json(route, { document_id: documentId, version_id: versionId, document_key: "vpn-admin-guide", title: "VPN admin guide", version_label: "v1", status: "draft", job_id: "30000000-0000-0000-0000-000000000001", byte_size: 120, parser_version: "pypdf-v1", pages: [{ page_number: 1, text: "Use the managed VPN client." }] }, 201);
  });
  await page.route("**/api/v1/documents/*/versions/*/preview", (route) =>
    json(route, { document_id: documentId, version_id: versionId, byte_size: 120, parser_version: "pypdf-v1", pages: [{ page_number: 1, text: "Use the managed VPN client." }] }),
  );
  await page.route("**/api/v1/documents/*/versions/*/process", async (route) => {
    versionStatus = "ready";
    await json(route, { status: "ready" });
  });
  await page.route("**/api/v1/documents/*/publish", async (route) => {
    versionStatus = "published";
    currentVersionId = versionId;
    documentVersion += 1;
    await json(route, responseDocument());
  });
  await page.route("**/api/v1/documents/*/revoke", async (route) => {
    versionStatus = "superseded";
    currentVersionId = null;
    archived = true;
    documentVersion += 1;
    await json(route, responseDocument());
  });

  await page.goto("/admin/documents");
  await page.getByLabel("PDF").first().setInputFiles({ name: "vpn.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-e2e") });
  await page.getByLabel("Document key").fill("vpn-admin-guide");
  await page.getByLabel("Tiêu đề").fill("VPN admin guide");
  await page.getByRole("button", { name: "Upload draft" }).click();
  await expect(page.getByRole("heading", { name: "VPN admin guide" })).toBeVisible();
  await expect(page.getByText("Use the managed VPN client.")).toBeVisible();
  await page.getByRole("button", { name: "Đóng" }).click();
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("Trang 1")).toBeVisible();
  await page.getByRole("button", { name: "Đóng" }).click();
  await page.getByRole("button", { name: "Process" }).click();
  await expect(page.getByRole("button", { name: "Publish" })).toBeVisible();
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByRole("button", { name: "Revoke" })).toBeVisible();
  await page.getByRole("button", { name: "Revoke" }).click();
  await expect(page.getByText("revoked", { exact: true })).toBeVisible();
});

test("employee cannot access document administration", async ({ page }) => {
  await mockSession(page, employee);
  let documentRequests = 0;
  await page.route("**/api/v1/documents", (route) => {
    documentRequests += 1;
    return json(route, { detail: "Insufficient role" }, 403);
  });
  await page.goto("/admin/documents");
  await expect(page.getByRole("alert")).toHaveText("Khu vực tài liệu chỉ dành cho quản trị viên.");
  expect(documentRequests).toBe(0);
});
