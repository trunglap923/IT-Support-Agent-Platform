import { describe, expect, it } from "vitest";

import type { ChatMessage } from "../../api/chat";
import type { Approval } from "../../api/tickets";
import { recoverActiveRun } from "./chatRecovery";

const runId = "22222222-2222-2222-2222-222222222222";

function message(values: Partial<ChatMessage>): ChatMessage {
  return {
    id: crypto.randomUUID(),
    run_id: null,
    role: "user",
    content: "hello",
    outcome: null,
    created_at: "2026-10-01T08:00:00Z",
    ...values,
  };
}

const approval: Approval = {
  id: "11111111-1111-1111-1111-111111111111",
  action_id: "agent-ticket:run",
  run_id: runId,
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
  expires_at: "2026-09-18T10:00:00Z",
};

describe("recoverActiveRun", () => {
  it("restores a pending approval after refresh", () => {
    const messages = [
      message({ run_id: runId }),
      message({
        run_id: runId,
        role: "assistant",
        outcome: "approval_required",
      }),
    ];
    expect(recoverActiveRun(messages, [approval])).toBe(runId);
  });

  it("does not reopen a completed answer", () => {
    const messages = [
      message({ run_id: runId }),
      message({ run_id: runId, role: "assistant", outcome: "ticket_created" }),
    ];
    expect(recoverActiveRun(messages, [])).toBeNull();
  });

  it("does not restore an approval-required run after its draft was cancelled", () => {
    const messages = [
      message({ run_id: runId }),
      message({
        run_id: runId,
        role: "assistant",
        outcome: "approval_required",
      }),
    ];

    expect(recoverActiveRun(messages, [])).toBeNull();
  });

  it("does not recover a run already observed as terminal", () => {
    const messages = [message({ run_id: runId })];

    expect(recoverActiveRun(messages, [], new Set([runId]))).toBeNull();
  });
});
