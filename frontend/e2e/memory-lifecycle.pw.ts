import { expect, test, type Page, type Route } from "@playwright/test";

const user = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  email: "employee@example.com",
  display_name: "Memory User",
  role: "employee",
  department_id: "22222222-2222-2222-2222-222222222222",
  department_key: "engineering",
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function mockSession(page: Page) {
  await page.route("**/api/v1/auth/me", (route) =>
    json(route, { user, csrf_token: "csrf-memory-e2e" }),
  );
}

test("always-on memory still requires confirmation and supports edit/delete", async ({ page }) => {
  await mockSession(page);
  const device = { id: "30000000-0000-0000-0000-000000000001", label: "Laptop công ty", platform: "windows", active: true, version: 1 };
  let devices: typeof device[] = [];
  let candidates = [{ id: "40000000-0000-0000-0000-000000000001", kind: "device", key: "operating_system", value: "Windows 11", evidence: "Tôi dùng Windows 11.", device_id: null, status: "pending", version: 1, expires_at: "2026-09-23T00:00:00Z" }];
  let facts: Array<{ id: string; kind: string; key: string; value: string; scope: "device"; device_id: string; version: number; expires_at: string }> = [];

  await page.route("**/api/v1/memory/devices", async (route) => {
    if (route.request().method() === "POST") devices = [device];
    await json(route, route.request().method() === "POST" ? device : devices, route.request().method() === "POST" ? 201 : 200);
  });
  await page.route("**/api/v1/memory/candidates**", (route) => json(route, { items: candidates, next_cursor: null }));
  await page.route("**/api/v1/memory/candidates/*/confirm", async (route) => {
    expect((await route.request().postDataJSON()).device_id).toBe(device.id);
    facts = [{ id: "50000000-0000-0000-0000-000000000001", kind: "device", key: "operating_system", value: "Windows 11", scope: "device", device_id: device.id, version: 1, expires_at: "2026-12-15T00:00:00Z" }];
    candidates = [];
    await json(route, facts[0]);
  });
  await page.route("**/api/v1/memory/facts**", (route) => json(route, { items: facts, next_cursor: null }));
  await page.route("**/api/v1/memory/facts/*", async (route) => {
    if (route.request().method() === "PATCH") {
      facts = [{ ...facts[0], value: "Windows 11 Enterprise", version: 2 }];
      await json(route, facts[0]);
      return;
    }
    facts = [];
    await route.fulfill({ status: 204 });
  });

  await page.goto("/settings/memory");
  await expect(page.getByText(/Memory luôn hoạt động/)).toBeVisible();
  await page.getByLabel("Tên thiết bị").fill("Laptop công ty");
  await page.getByRole("button", { name: "Thêm thiết bị" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: "Laptop công ty" })).toBeVisible();
  await page.locator('select[name="device_id"]').selectOption(device.id);
  await page.getByRole("button", { name: "Xác nhận" }).click();
  await expect(page.getByText("operating_system · Laptop công ty")).toBeVisible();
  await page.getByLabel("Giá trị").last().fill("Windows 11 Enterprise");
  await page.getByRole("button", { name: "Lưu sửa đổi" }).click();
  await expect(page.locator('input[name="value"]').last()).toHaveValue("Windows 11 Enterprise");
  await page.getByRole("button", { name: "Xóa" }).click();
  await page.getByRole("button", { name: "Xóa memory" }).click();
  await expect(page.getByText("Chưa có memory nào được xác nhận.")).toBeVisible();
});
