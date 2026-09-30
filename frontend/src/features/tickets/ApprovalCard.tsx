import { useEffect, useState } from "react";

import type { Approval } from "../../api/tickets";
import { ConfirmDialog } from "../../components/ProductUI";

interface ApprovalCardProps {
  approval: Approval;
  onDecision: (decision: "approve" | "reject") => Promise<void>;
  onEdit: () => Promise<void>;
}

export function ApprovalCard({ approval, onDecision, onEdit }: ApprovalCardProps) {
  const [busy, setBusy] = useState<"approve" | "reject" | "edit" | null>(null);
  const [expired, setExpired] = useState(
    () => Date.parse(approval.expires_at) <= Date.now(),
  );
  const [confirmReject, setConfirmReject] = useState(false);
  const values = approval.canonical_args;

  useEffect(() => {
    let timer: number | undefined;
    const schedule = () => {
      const remaining = Date.parse(approval.expires_at) - Date.now();
      if (remaining <= 0) {
        setExpired(true);
        return;
      }
      timer = window.setTimeout(schedule, Math.min(remaining, 2_147_000_000));
    };
    schedule();
    return () => window.clearTimeout(timer);
  }, [approval.expires_at]);

  async function decide(decision: "approve" | "reject") {
    setBusy(decision);
    try {
      await onDecision(decision);
      setConfirmReject(false);
    } finally {
      setBusy(null);
    }
  }

  async function edit() {
    setBusy("edit");
    try {
      await onEdit();
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="approval-card">
      <div>
        <span className="approval-badge">{expired ? "Đã hết hạn" : "Cần xác nhận"}</span>
        <h3>{values.title}</h3>
        <p>{values.description}</p>
        <small>{values.issue_type} · {values.severity} · hết hạn {new Date(approval.expires_at).toLocaleString("vi-VN")}</small>
      </div>
      <div className="approval-actions">
        <button disabled={expired || busy !== null} onClick={() => void edit()} type="button">
          {busy === "edit" ? "Đang mở bản sửa…" : "Sửa bản nháp"}
        </button>
        <button disabled={expired || busy !== null} onClick={() => setConfirmReject(true)} type="button">
          Từ chối
        </button>
        <button className="primary-button" disabled={expired || busy !== null} onClick={() => void decide("approve")} type="button">
          {busy === "approve" ? "Đang xác nhận…" : "Xác nhận tạo ticket"}
        </button>
      </div>
      <ConfirmDialog
        busy={busy === "reject"}
        confirmLabel="Từ chối bản nháp"
        description="Bản nháp sẽ bị hủy và ticket sẽ không được tạo."
        onCancel={() => setConfirmReject(false)}
        onConfirm={() => void decide("reject")}
        open={confirmReject}
        title="Từ chối bản nháp?"
        tone="danger"
      />
    </article>
  );
}
