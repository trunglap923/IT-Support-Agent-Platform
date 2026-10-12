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
    json(route, { user: employee, csrf_token: "csrf-chat-workspace" }),
  );
}

test("chat shows grouped history, message actions, device and ticket context", async ({ page }) => {
  const now = new Date();
  const recent = now.toISOString();
  const yesterday = new Date(now.getTime() - 86_400_000).toISOString();
  const conversationId = "55555555-5555-5555-5555-555555555555";
  let currentMessages: unknown[];
  const assistantMessage = {
    id: "77777777-7777-7777-7777-777777777777",
    run_id: "66666666-6666-6666-6666-666666666666",
    role: "assistant",
    content: "Hãy kiểm tra theo các bước sau:\n\n1. **Kiểm tra kết nối mạng**\n   - Mở một trang web nội bộ.\n2. **Khởi động lại VPN**\n   - Kết nối lại bằng VPN Client.",
    outcome: "answered",
    created_at: recent,
    citations: [{
      source_id: "source-vpn-guide",
      title: "Hướng dẫn sử dụng VPN",
      page_number: 2,
      excerpt: "Mở VPN Client và kiểm tra trạng thái kết nối.",
    }],
    feedback: null,
  };

  await mockSession(page);
  await page.route("**/api/v1/conversations?**", (route) => json(route, {
    items: [
      {
        id: conversationId, title: "Không kết nối được VPN", device_id: "device-1",
        created_at: yesterday, updated_at: recent, preview: "Hãy kiểm tra theo các bước sau",
        preview_at: recent, preview_role: "assistant",
      },
      {
        id: "88888888-8888-8888-8888-888888888888", title: "Đặt lại mật khẩu",
        device_id: null, created_at: yesterday, updated_at: yesterday,
        preview: "Hướng dẫn đặt lại mật khẩu AD", preview_at: yesterday, preview_role: "assistant",
      },
    ],
    next_cursor: null,
  }));
  currentMessages = [
      {
        id: "99999999-9999-9999-9999-999999999999",
        run_id: "66666666-6666-6666-6666-666666666666",
        role: "user", content: "VPN không kết nối được trên máy tính ở nhà.",
        outcome: null, created_at: recent, citations: [], feedback: null,
      },
      assistantMessage,
  ];
  await page.route("**/api/v1/conversations/*/messages**", (route) => {
    if (route.request().method() === "POST") {
      currentMessages = [{
        id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        run_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        role: "user", content: "Tôi tên là gì?", outcome: null,
        created_at: new Date().toISOString(), citations: [], feedback: null,
      }];
      return json(route, {
        run_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        status: "running", created: true, enqueued: true, enqueue_error: null,
      }, 202);
    }
    return json(route, { items: currentMessages, next_cursor: null });
  });
  await page.route("**/api/v1/runs/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", (route) => json(route, {
    id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", conversation_id: conversationId,
    status: "running", outcome: null, version: 1, error_code: null,
  }));
  await page.route("**/api/v1/runs/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/events**", (route) => {
    const timestamp = new Date().toISOString();
    const events = [
      { sequence: 1, type: "run.running", payload: {} },
      { sequence: 2, type: "agent.progress", payload: { stage: "analyze", status: "completed", detail: "Đã xác định nội dung cần hỗ trợ." } },
      { sequence: 3, type: "agent.progress", payload: { stage: "profile", status: "started", detail: "Đang đọc thông tin tài khoản." } },
      { sequence: 4, type: "agent.progress", payload: { stage: "answer", status: "pending" } },
    ].map((event) => ({
      ...event, run_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", timestamp,
    }));
    const body = events.map((event) => `id: ${event.sequence}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join("");
    return route.fulfill({ status: 200, contentType: "text/event-stream", body });
  });
  await page.route("**/api/v1/approvals?approval_status=pending**", (route) =>
    json(route, { items: [], next_cursor: null }),
  );
  await page.route("**/api/v1/tickets/mine**", (route) => json(route, {
    items: [{
      id: "ticket-1", display_key: "IT-8159", title: "Không truy cập được VPN",
      description: "VPN disconnects", issue_type: "vpn", severity: "normal",
      status: "in_progress", resolution_note: null, version: 1,
      created_at: recent, updated_at: recent, requester_name: "Demo Engineer",
    }],
    next_cursor: null,
  }));
  await page.route("**/api/v1/memory/devices", (route) => json(route, [{
    id: "device-1", label: "DEMO-LT-001", platform: "windows", active: true,
    version: 1, created_at: yesterday, updated_at: recent,
  }]));
  await page.route("**/api/v1/conversations/*/messages/*/feedback", (route) => json(route, {
    id: "feedback-1", message_id: assistantMessage.id, rating: "helpful", reason: null, comment: null,
  }));

  await page.setViewportSize({ width: 1680, height: 940 });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/chat");

  await expect(page.getByText("Hôm nay", { exact: true })).toBeVisible();
  await expect(page.getByText("Hôm qua", { exact: true })).toBeVisible();
  await expect(page.getByText("DEMO-LT-001")).toBeVisible();
  await expect(page.getByText("Đang xử lý", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Đề xuất hành động" })).toBeVisible();
  await expect(page.getByText("Kiểm tra kết nối mạng")).toBeVisible();

  await page.screenshot({ path: "/tmp/chat-workspace-desktop.png", fullPage: true });
  await page.getByRole("button", { name: "Sao chép" }).click();
  await expect(page.getByRole("button", { name: "Đã sao chép" })).toBeVisible();
  await page.getByRole("button", { name: /Tạo ticket/ }).first().click();
  await expect(page.getByLabel("Tin nhắn")).toHaveValue(/Tạo ticket hỗ trợ/);

  await page.getByLabel("Tin nhắn").fill("Tôi tên là gì?");
  await page.getByLabel("Tin nhắn").press("Control+Enter");
  await expect(page.getByRole("heading", { name: "Đang xử lý yêu cầu của bạn…" })).toBeVisible();
  await expect(page.getByText("Đọc thông tin tài khoản", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Xem chi tiết" }).click();
  await expect(page.getByText("Tổng hợp hướng xử lý")).toBeVisible();
  await expect(page.getByText("Tìm kiếm kho tri thức")).toHaveCount(0);
  await page.screenshot({ path: "/tmp/chat-agent-progress-desktop.png", fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.locator(".menu-button")).toBeVisible();
  await expect(page.locator(".app-sidebar")).not.toHaveClass(/open/);
  await expect(page.locator(".conversation-list")).toBeHidden();
  await page.screenshot({ path: "/tmp/chat-workspace-mobile.png", fullPage: true });

  await page.getByRole("button", { name: "Mở danh sách hội thoại" }).click();
  await expect(page.locator(".conversation-list")).toBeVisible();
  await expect(page.getByRole("button", { name: "Đóng danh sách hội thoại" }).first()).toBeFocused();
  await page.screenshot({ path: "/tmp/chat-conversations-mobile.png", fullPage: true });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Mở danh sách hội thoại" })).toBeFocused();

  const contextToggle = page.getByRole("button", { name: "Mở ngữ cảnh hỗ trợ" });
  await expect(contextToggle).toBeVisible();
  await contextToggle.click();
  await expect(page.getByRole("dialog", { name: "Ngữ cảnh hỗ trợ và ticket" })).toBeVisible();
  await expect(page.locator(".chat-context-summary")).toBeFocused();
  await expect(page.getByText("DEMO-LT-001")).toBeVisible();
  await page.screenshot({ path: "/tmp/chat-context-mobile.png", fullPage: true });
  await page.keyboard.press("Escape");
  await expect(contextToggle).toBeFocused();
});
