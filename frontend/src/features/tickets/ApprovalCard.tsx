import { useState } from "react";

import type { Approval } from "../../api/tickets";

interface ApprovalCardProps {
  approval: Approval;
  onDecision: (decision: "approve" | "reject") => Promise<void>;
}

export function ApprovalCard({ approval, onDecision }: ApprovalCardProps) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const values = approval.canonical_args;

  async function decide(decision: "approve" | "reject") {
    setBusy(decision);
    try {
      await onDecision(decision);
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="approval-card">
      <div>
        <span className="approval-badge">Cần xác nhận</span>
        <h3>{values.title}</h3>
        <p>{values.description}</p>
        <small>{values.issue_type} · {values.severity} · hết hạn {new Date(approval.expires_at).toLocaleString("vi-VN")}</small>
      </div>
      <div className="approval-actions">
        <button disabled={busy !== null} onClick={() => void decide("reject")} type="button">
          {busy === "reject" ? "Đang từ chối…" : "Từ chối"}
        </button>
        <button className="primary-button" disabled={busy !== null} onClick={() => void decide("approve")} type="button">
          {busy === "approve" ? "Đang xác nhận…" : "Xác nhận tạo ticket"}
        </button>
      </div>
    </article>
  );
}
