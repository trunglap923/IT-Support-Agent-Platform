import type { ChatMessage } from "../../api/chat";
import type { Approval } from "../../api/tickets";

export function recoverActiveRun(
  messages: ChatMessage[],
  approvals: Approval[],
): string | null {
  const pending = approvals.find((approval) =>
    messages.some((message) => message.run_id === approval.run_id),
  );
  if (pending) return pending.run_id;
  const last = messages.at(-1);
  if (!last?.run_id) return null;
  if (last.role === "user") return last.run_id;
  return null;
}
