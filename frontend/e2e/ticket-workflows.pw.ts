import { expect, test, type Page, type Route } from "@playwright/test";

const employee = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "employee.engineering@example.com",
  display_name: "Demo Engineer",
  role: "employee",
  department_id: "22222222-2222-2222-2222-222222222222",
  department_key: "engineering",
};

const itUser = { ...employee, email: "it.engineering@example.com", display_name: "IT Engineer", role: "it" };
const adminUser = { ...employee, email: "admin@example.com", display_name: "Admin", role: "admin" };

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

function cursorPage(items: unknown[]) {
  return { items, next_cursor: null };
}

async function mockSession(page: Page, user = employee) {
  await page.route("**/api/v1/auth/me", (route) =>
    json(route, { user, csrf_token: "csrf-browser-test" }),
  );
}

test("employee creates, approves and rejects ticket drafts", async ({ page }) => {
  await mockSession(page);
  const pending: Record<string, unknown>[] = [];
  const cancelledRuns: string[] = [];
  let draftCounter = 0;

  await page.route("**/api/v1/tickets/mine**", (route) => json(route, cursorPage([])));
  await page.route("**/api/v1/approvals?approval_status=pending**", (route) =>
    json(route, cursorPage(pending)),
  );
  await page.route("**/api/v1/tickets/drafts", async (route) => {
    const request = route.request();
    expect(request.headers()["x-csrf-token"]).toBe("csrf-browser-test");
    const body = request.postDataJSON();
    draftCounter += 1;
    const approval = {
      id: `00000000-0000-0000-0000-00000000000${draftCounter}`,
      action_id: `ticket:${draftCounter}`,
      run_id: `10000000-0000-0000-0000-00000000000${draftCounter}`,
      tool_name: "create_ticket",
      canonical_args: {
        title: body.title,
        description: body.description,
        issue_type: body.issue_type,
        severity: body.severity,
        device_id: null,
      },
      arguments_hash: "a".repeat(64),
      schema_version: 1,
      status: "pending",
      version: 1,
      expires_at: "2099-09-17T10:00:00Z",
    };
    pending.unshift(approval);
    await json(route, { run_id: approval.run_id, approval, created: true }, 201);
  });
  await page.route("**/api/v1/approvals/*/decision", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.expected_version).toBe(1);
    const id = route.request().url().split("/").at(-2);
    const approval = pending.find((item) => item.id === id);
    pending.splice(pending.findIndex((item) => item.id === id), 1);
    await json(route, { ...approval, status: body.decision === "approve" ? "approved" : "rejected", version: 2 });
  });
  await page.route("**/api/v1/runs/**", async (route) => {
    const request = route.request();
    const parts = request.url().split("/");
    const runId = parts.at(-1) === "cancel" ? parts.at(-2)! : parts.at(-1)!;
    if (request.method() === "GET") {
      await json(route, {
        id: runId,
        conversation_id: "20000000-0000-0000-0000-000000000001",
        status: "waiting_approval",
        outcome: "approval_required",
        version: 2,
        error_code: null,
      });
      return;
    }
    const body = request.postDataJSON();
    expect(body).toEqual({ expected_version: 2, reason: "draft_replaced" });
    cancelledRuns.push(runId);
    const index = pending.findIndex((item) => item.run_id === runId);
    if (index >= 0) pending.splice(index, 1);
    await json(route, {
      id: runId,
      conversation_id: "20000000-0000-0000-0000-000000000001",
      status: "cancelled",
      outcome: "draft_replaced",
      version: 3,
      error_code: null,
    });
  });

  await page.goto("/tickets");
  await page.getByLabel("Tiêu đề").fill("VPN access issue");
  await page.getByLabel("Mô tả").fill("VPN remains unavailable after all documented steps.");
  await page.getByLabel("Loại sự cố", { exact: true }).selectOption("vpn");
  await page.getByRole("button", { name: "Tạo bản nháp" }).click();
  await expect(page.getByRole("heading", { name: "VPN access issue" })).toBeVisible();
  await page.getByRole("button", { name: "Sửa bản nháp" }).click();
  await expect(page.getByText("Đã hủy bản nháp cũ. Hãy chỉnh sửa rồi tạo bản nháp mới.")).toBeVisible();
  await expect(page.getByLabel("Tiêu đề")).toHaveValue("VPN access issue");
  await page.getByLabel("Tiêu đề").fill("VPN access issue updated");
  await page.getByRole("button", { name: "Tạo bản nháp" }).click();
  await expect(page.getByRole("heading", { name: "VPN access issue updated" })).toBeVisible();
  await page.getByRole("button", { name: "Xác nhận tạo ticket" }).click();
  await expect(page.getByText("Đã xác nhận. Worker đang tạo ticket an toàn.")).toBeVisible();
  expect(cancelledRuns).toEqual(["10000000-0000-0000-0000-000000000001"]);

  await page.getByLabel("Tiêu đề").fill("GitLab access issue");
  await page.getByLabel("Mô tả").fill("GitLab access is denied for the required project.");
  await page.getByLabel("Loại sự cố", { exact: true }).selectOption("gitlab");
  await page.getByRole("button", { name: "Tạo bản nháp" }).click();
  await page.getByRole("button", { name: "Từ chối" }).click();
  await page.getByRole("button", { name: "Từ chối bản nháp" }).click();
  await expect(page.getByText("Đã từ chối bản nháp.")).toBeVisible();
});

test("retrying an unchanged ticket draft reuses its client request id", async ({ page }) => {
  await mockSession(page);
  const requestIds: string[] = [];

  await page.route("**/api/v1/tickets/mine**", (route) => json(route, cursorPage([])));
  await page.route("**/api/v1/approvals?approval_status=pending**", (route) =>
    json(route, cursorPage([])),
  );
  await page.route("**/api/v1/tickets/drafts", async (route) => {
    const body = route.request().postDataJSON();
    requestIds.push(body.client_request_id);
    if (requestIds.length === 1) {
      await json(route, { error: { code: "dependency_unavailable", message: "Unavailable" } }, 503);
      return;
    }
    const approval = {
      id: "00000000-0000-0000-0000-000000000099",
      action_id: "ticket:retry",
      run_id: "10000000-0000-0000-0000-000000000099",
      tool_name: "create_ticket",
      canonical_args: {
        title: body.title,
        description: body.description,
        issue_type: body.issue_type,
        severity: body.severity,
        device_id: null,
      },
      arguments_hash: "b".repeat(64),
      schema_version: 1,
      status: "pending",
      version: 1,
      expires_at: "2099-09-17T10:00:00Z",
    };
    await json(route, { run_id: approval.run_id, approval, created: true }, 201);
  });

  await page.goto("/tickets");
  await page.getByLabel("Tiêu đề").fill("Retry-safe VPN request");
  await page.getByLabel("Mô tả").fill("VPN remains unavailable after documented troubleshooting.");
  await page.getByRole("button", { name: "Tạo bản nháp" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "Tạo bản nháp" }).click();
  await expect(page.getByRole("heading", { name: "Retry-safe VPN request" })).toBeVisible();

  expect(requestIds).toHaveLength(2);
  expect(requestIds[1]).toBe(requestIds[0]);
});

test("approval UI blocks double decisions and expired drafts", async ({ page }) => {
  await mockSession(page);
  let decisionCount = 0;
  const approval = (id: string, title: string, expiresAt: string) => ({
    id,
    action_id: `ticket:${id}`,
    run_id: id.replace(/^0/, "1"),
    tool_name: "create_ticket",
    canonical_args: {
      title,
      description: "VPN remains unavailable after documented troubleshooting.",
      issue_type: "vpn",
      severity: "normal",
      device_id: null,
    },
    arguments_hash: "c".repeat(64),
    schema_version: 1,
    status: "pending",
    version: 1,
    expires_at: expiresAt,
  });
  const activeApproval = approval(
    "00000000-0000-0000-0000-000000000081",
    "Double approve protection",
    "2099-09-17T10:00:00Z",
  );
  const expiredApproval = approval(
    "00000000-0000-0000-0000-000000000082",
    "Expired approval",
    "2020-09-17T10:00:00Z",
  );

  await page.route("**/api/v1/tickets/mine**", (route) => json(route, cursorPage([])));
  await page.route("**/api/v1/approvals?approval_status=pending**", (route) =>
    json(route, cursorPage([activeApproval, expiredApproval])),
  );
  await page.route("**/api/v1/approvals/*/decision", async (route) => {
    decisionCount += 1;
    await new Promise((resolve) => setTimeout(resolve, 100));
    await json(route, { ...activeApproval, status: "approved", version: 2 });
  });

  await page.goto("/tickets");
  const activeCard = page.locator(".approval-card").filter({ hasText: "Double approve protection" });
  const expiredCard = page.locator(".approval-card").filter({ hasText: "Expired approval" });

  await expect(expiredCard.getByText("Đã hết hạn")).toBeVisible();
  await expect(expiredCard.getByRole("button", { name: "Xác nhận tạo ticket" })).toBeDisabled();
  await activeCard.getByRole("button", { name: "Xác nhận tạo ticket" }).dblclick();
  await expect(page.getByText("Đã xác nhận. Worker đang tạo ticket an toàn.")).toBeVisible();
  expect(decisionCount).toBe(1);
});

test("IT resolves and reopens tickets", async ({ page }) => {
  await mockSession(page, itUser);
  let ticket = {
    id: "33333333-3333-3333-3333-333333333333",
    display_key: "IT-E2E-1",
    title: "VPN unavailable",
    description: "Employee cannot connect to VPN.",
    issue_type: "vpn",
    severity: "normal",
    status: "open",
    resolution_note: null as string | null,
    version: 1,
  };
  const service = {
    service_id: "vpn",
    status: "healthy",
    message: "VPN is operating normally.",
    fault_mode: "none",
    updated_at: "2026-09-16T00:00:00Z",
  };
  await page.route("**/api/v1/tickets/queue**", (route) => json(route, cursorPage([ticket])));
  await page.route("**/api/v1/service-status", (route) => json(route, [service]));
  await page.route("**/api/v1/tickets/*/transition", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.expected_version).toBe(ticket.version);
    const nextStatus = body.action === "start" ? "in_progress" : body.action === "resolve" ? "resolved" : "open";
    ticket = { ...ticket, status: nextStatus, version: ticket.version + 1, resolution_note: body.action === "resolve" ? body.resolution_note : null };
    await json(route, ticket);
  });

  await page.goto("/operations");
  await page.getByRole("button", { name: "Bắt đầu xử lý" }).click();
  await page.getByLabel("Ghi chú xử lý IT-E2E-1").fill("Profile reissued and connectivity verified.");
  await page.getByRole("button", { name: "Resolve" }).click();
  await expect(page.getByText(/IT-E2E-1 · resolved/)).toBeVisible();
  await page.getByRole("button", { name: "Reopen" }).click();
  await expect(page.getByText(/IT-E2E-1 · open/)).toBeVisible();

  await expect(page.getByLabel("Trạng thái vpn")).toBeDisabled();
  await expect(page.getByText("Chỉ quản trị viên được thay đổi trạng thái mô phỏng.")).toBeVisible();
});

test("admin updates simulated service state", async ({ page }) => {
  await mockSession(page, adminUser);
  let service = {
    service_id: "vpn",
    status: "healthy",
    message: "VPN is operating normally.",
    fault_mode: "none",
    updated_at: "2026-09-16T00:00:00Z",
  };
  await page.route("**/api/v1/tickets/queue**", (route) => json(route, cursorPage([])));
  await page.route("**/api/v1/service-status", (route) => json(route, [service]));
  await page.route("**/api/v1/service-status/vpn", async (route) => {
    service = { ...service, ...route.request().postDataJSON() };
    await json(route, service);
  });
  await page.goto("/operations");
  await page.getByLabel("Trạng thái vpn").selectOption("degraded");
  await page.getByLabel("Thông báo vpn").fill("VPN latency is elevated.");
  await page.getByRole("button", { name: "Lưu" }).click();
  await expect(page.getByLabel("Trạng thái vpn")).toHaveValue("degraded");
});

test("employee cannot enter IT operations", async ({ page }) => {
  await mockSession(page);
  let operationsRequestCount = 0;
  await page.route("**/api/v1/tickets/queue", (route) => {
    operationsRequestCount += 1;
    return json(route, { detail: "Insufficient role" }, 403);
  });
  await page.goto("/operations");
  await expect(page.getByRole("alert")).toHaveText("Khu vực này chỉ dành cho IT hoặc quản trị viên.");
  expect(operationsRequestCount).toBe(0);
});
