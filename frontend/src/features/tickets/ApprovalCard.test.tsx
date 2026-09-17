import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Approval } from "../../api/tickets";
import { ApprovalCard } from "./ApprovalCard";

const approval: Approval = {
  id: "11111111-1111-1111-1111-111111111111",
  action_id: "ticket:one",
  run_id: "22222222-2222-2222-2222-222222222222",
  tool_name: "create_ticket",
  canonical_args: {
    title: "VPN access issue",
    description: "VPN remains unavailable after troubleshooting.",
    issue_type: "vpn",
    severity: "normal",
    device_id: null,
  },
  arguments_hash: "a".repeat(64),
  schema_version: 1,
  status: "pending",
  version: 1,
  expires_at: "2099-09-16T10:00:00Z",
};

describe("ApprovalCard", () => {
  it("shows immutable draft details and submits explicit approval", async () => {
    const onDecision = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalCard approval={approval} onDecision={onDecision} />);

    expect(screen.getByRole("heading", { name: "VPN access issue" })).toBeInTheDocument();
    expect(screen.getByText(/VPN remains unavailable/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận tạo ticket" }));

    await waitFor(() => expect(onDecision).toHaveBeenCalledWith("approve"));
  });

  it("supports rejection without presenting it as ticket creation", async () => {
    const onDecision = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalCard approval={approval} onDecision={onDecision} />);
    fireEvent.click(screen.getByRole("button", { name: "Từ chối" }));
    await waitFor(() => expect(onDecision).toHaveBeenCalledWith("reject"));
  });

  it("disables decisions for an expired draft", () => {
    const onDecision = vi.fn().mockResolvedValue(undefined);
    render(
      <ApprovalCard
        approval={{ ...approval, expires_at: "2020-01-01T00:00:00Z" }}
        onDecision={onDecision}
      />,
    );
    expect(screen.getByText("Đã hết hạn")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Từ chối" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Xác nhận tạo ticket" })).toBeDisabled();
  });
});
