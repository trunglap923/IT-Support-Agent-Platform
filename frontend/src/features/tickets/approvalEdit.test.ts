import { describe, expect, it } from "vitest";

import { formatTicketDraftForChat } from "./approvalEdit";

describe("formatTicketDraftForChat", () => {
  it("preserves editable ticket fields for a new chat run", () => {
    expect(
      formatTicketDraftForChat({
        title: "VPN access issue",
        description: "VPN remains unavailable after troubleshooting.",
        issue_type: "vpn",
        severity: "high",
        device_id: "device-1",
      }),
    ).toBe(
      "Tạo ticket hỗ trợ với thông tin sau:\n" +
        "Tiêu đề: VPN access issue\n" +
        "Mô tả: VPN remains unavailable after troubleshooting.\n" +
        "Loại sự cố: vpn\n" +
        "Mức độ: high\n" +
        "Thiết bị: device-1",
    );
  });
});
