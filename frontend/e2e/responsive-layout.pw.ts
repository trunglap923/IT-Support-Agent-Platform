import { expect, test, type Page, type Route } from "@playwright/test";

const user = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "employee.engineering@example.com",
  display_name: "Demo Engineer",
  role: "employee",
  department_id: "22222222-2222-2222-2222-222222222222",
  department_key: "engineering",
};
const itUser = { ...user, display_name: "IT Engineer", email: "it.engineering@example.com", role: "it" };
const adminUser = { ...user, display_name: "Document Admin", email: "admin@example.com", role: "admin" };

const tickets = [
  {
    id: "33333333-3333-3333-3333-333333333333",
    display_key: "IT-2048",
    title: "VPN connection fails from home",
    description: "The managed VPN client cannot establish a connection from the home network.",
    issue_type: "vpn",
    severity: "high",
    status: "open",
    resolution_note: null,
    version: 1,
  },
  {
    id: "44444444-4444-4444-4444-444444444444",
    display_key: "IT-2047",
    title: "Docker registry authentication",
    description: "Registry login requires a refreshed short-lived access token.",
    issue_type: "docker",
    severity: "normal",
    status: "in_progress",
    resolution_note: null,
    version: 2,
  },
];

function json(route: Route, body: unknown) {
  return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockWorkspace(page: Page, actor = user) {
  await page.route("**/api/v1/auth/me", (route) => json(route, { user: actor, csrf_token: "csrf-visual" }));
  await page.route("**/api/v1/tickets/mine", (route) => json(route, tickets));
  await page.route("**/api/v1/approvals?approval_status=pending", (route) => json(route, []));
  await page.route("**/api/v1/health/live", (route) => json(route, {
    status: "ok",
    service: "api",
    version: "1.0",
    environment: "demo",
    provider: "fake",
    request_id: "visual-check",
  }));
}

async function mockChat(page: Page) {
  await mockWorkspace(page);
  await page.route("**/api/v1/conversations", (route) => json(route, [
    { id: "55555555-5555-5555-5555-555555555555", title: "VPN trên Ubuntu" },
    { id: "66666666-6666-6666-6666-666666666666", title: "Docker registry" },
  ]));
  await page.route("**/api/v1/conversations/*/messages", (route) => json(route, [
    {
      id: "77777777-7777-7777-7777-777777777777",
      run_id: null,
      role: "user",
      content: "Cách cấu hình VPN trên Ubuntu như thế nào?",
      outcome: null,
    },
    {
      id: "88888888-8888-8888-8888-888888888888",
      run_id: null,
      role: "assistant",
      content: "Tôi đã tìm thấy hướng dẫn nội bộ liên quan:\n\n1. Cài managed VPN client.\n2. Nhập URL công ty và đăng nhập SSO.\n3. Không tắt kiểm tra chứng chỉ.",
      outcome: "answered",
      citations: [{
        source_id: "vpn-guide",
        title: "Thiết lập VPN demo",
        page_number: 1,
        excerpt: "Ubuntu: cài client, nhập URL công ty demo và đăng nhập SSO.",
      }],
      feedback: null,
    },
  ]));
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
}

test("dashboard remains compact on desktop", async ({ page }, testInfo) => {
  await mockWorkspace(page);
  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Chào Demo" })).toBeVisible();
  await expect(page.getByText("IT-2048")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("dashboard-desktop.png"), fullPage: true });
});

test("mobile navigation and dashboard do not overflow", async ({ page }, testInfo) => {
  await mockWorkspace(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Mở điều hướng" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.getByRole("button", { name: "Mở điều hướng" }).click();
  await expect(page.getByRole("navigation", { name: "Điều hướng chính" })).toBeVisible();
  await page.waitForTimeout(250);
  await page.screenshot({ path: testInfo.outputPath("dashboard-mobile.png"), fullPage: true });
});

test("chat stays readable on desktop and mobile", async ({ page }, testInfo) => {
  await mockChat(page);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/chat");
  await expect(page.getByText("Không tắt kiểm tra chứng chỉ.")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("chat-desktop.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  await expectNoHorizontalOverflow(page);
  const messageListWidth = await page.locator(".message-list").evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(messageListWidth.scrollWidth).toBeLessThanOrEqual(messageListWidth.clientWidth + 1);
  await page.screenshot({ path: testInfo.outputPath("chat-mobile.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("operations tables remain usable on desktop and mobile", async ({ page }, testInfo) => {
  await mockWorkspace(page, itUser);
  await page.route("**/api/v1/tickets/queue", (route) => json(route, tickets));
  await page.route("**/api/v1/service-status", (route) => json(route, [
    {
      service_id: "vpn",
      status: "healthy",
      message: "VPN is operating normally.",
      fault_mode: "none",
      updated_at: "2026-09-30T02:00:00Z",
    },
    {
      service_id: "gitlab",
      status: "degraded",
      message: "Repository operations are slower than normal.",
      fault_mode: "timeout",
      updated_at: "2026-09-30T02:05:00Z",
    },
  ]));

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/operations");
  await expect(page.getByRole("heading", { name: "Hàng đợi hỗ trợ" })).toBeVisible();
  await expect(page.getByText("IT-2048 · open · high")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("operations-desktop.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("operations-mobile.png"), fullPage: true });
});

test("document library remains usable on desktop and mobile", async ({ page }, testInfo) => {
  await mockWorkspace(page, adminUser);
  await page.route("**/api/v1/documents", (route) => json(route, [{
    id: "99999999-9999-9999-9999-999999999999",
    document_key: "vpn-admin-guide",
    title: "VPN administration guide",
    visibility: "company",
    department_id: null,
    archived: false,
    current_version_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    access_version: 3,
    version: 4,
    granted_department_ids: [],
    versions: [{
      id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      version_label: "v3",
      status: "published",
      authority: "IT Operations",
      language: "vi",
      effective_at: "2026-09-30T02:00:00Z",
      expires_at: null,
      created_at: "2026-09-30T02:00:00Z",
    }],
  }]));

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/admin/documents");
  await expect(page.getByRole("heading", { name: "VPN administration guide" })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("documents-desktop.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  await expectNoHorizontalOverflow(page);
  await expect(page.getByText("Vuốt ngang để quản lý version →")).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("documents-mobile.png"), fullPage: true });
});

test("memory workspace remains clear on desktop and mobile", async ({ page }, testInfo) => {
  await mockWorkspace(page);
  await page.route("**/api/v1/memory/devices", (route) => json(route, [{
    id: "12121212-1212-1212-1212-121212121212",
    label: "Laptop công ty",
    platform: "windows",
    active: true,
    version: 1,
  }]));
  await page.route("**/api/v1/memory/candidates", (route) => json(route, [{
    id: "13131313-1313-1313-1313-131313131313",
    kind: "device",
    key: "operating_system",
    value: "Windows 11 Enterprise",
    evidence: "Người dùng xác nhận đang sử dụng Windows 11 Enterprise trên laptop công ty.",
    device_id: null,
    status: "pending",
    version: 1,
    expires_at: "2026-12-30T02:00:00Z",
  }]));
  await page.route("**/api/v1/memory/facts", (route) => json(route, [{
    id: "14141414-1414-1414-1414-141414141414",
    kind: "preference",
    key: "preferred_language",
    value: "Tiếng Việt",
    scope: "global",
    device_id: null,
    version: 2,
    expires_at: "2027-03-30T02:00:00Z",
  }]));

  await page.setViewportSize({ width: 1440, height: 960 });
  await page.goto("/settings/memory");
  await expect(page.getByRole("heading", { name: "Memory & thiết bị" })).toBeVisible();
  await expect(page.getByText("preferred_language · Mọi thiết bị")).toBeVisible();
  await expect(page.getByRole("button", { name: "Xác nhận" })).toHaveCSS("background-color", "rgb(49, 95, 196)");
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("memory-desktop.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(250);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("memory-mobile.png"), fullPage: true });
});
