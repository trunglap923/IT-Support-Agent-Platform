import { expect, test, type Page, type Route } from "@playwright/test";

const employee = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "employee.engineering@example.com",
  display_name: "Demo Engineer",
  role: "employee",
  department_id: "22222222-2222-2222-2222-222222222222",
  department_key: "engineering",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockSession(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    json(route, { user: employee, csrf_token: "csrf-chat-retry" }),
  );
}

test("retrying an unchanged chat message reuses its client request id", async ({ page }) => {
  await mockSession(page);
  const requestIds: string[] = [];

  await page.route("**/api/v1/conversations?**", (route) => json(route, {
    items: [{
      id: "55555555-5555-5555-5555-555555555555", title: "VPN support", device_id: null,
      created_at: "2026-10-01T08:00:00Z", updated_at: "2026-10-01T08:00:00Z",
      preview: null, preview_at: null, preview_role: null,
    }],
    next_cursor: null,
  }));
  await page.route("**/api/v1/approvals?approval_status=pending**", (route) =>
    json(route, { items: [], next_cursor: null }),
  );
  await page.route("**/api/v1/tickets/mine**", (route) =>
    json(route, { items: [], next_cursor: null }),
  );
  await page.route("**/api/v1/memory/devices", (route) => json(route, []));
  await page.route("**/api/v1/conversations/*/messages**", async (route) => {
    if (route.request().method() === "GET") {
      await json(route, { items: [], next_cursor: null });
      return;
    }
    const body = route.request().postDataJSON();
    requestIds.push(body.client_request_id);
    if (requestIds.length === 1) {
      await json(route, { error: { code: "dependency_unavailable", message: "Unavailable" } }, 503);
      return;
    }
    await json(route, {
      run_id: "66666666-6666-6666-6666-666666666666",
      status: "queued",
      created: true,
      enqueued: true,
      enqueue_error: null,
    }, 202);
  });

  await page.goto("/chat");
  const composer = page.getByLabel("Tin nhắn");
  await composer.fill("VPN không kết nối được sau khi cập nhật client.");
  await page.getByRole("button", { name: "Gửi" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "Gửi" }).click();
  await expect(composer).toHaveValue("");

  expect(requestIds).toHaveLength(2);
  expect(requestIds[1]).toBe(requestIds[0]);
});
