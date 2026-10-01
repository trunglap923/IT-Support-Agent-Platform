import type { ChatMessage } from "../../api/chat";
import type { Approval } from "../../api/tickets";

export function recoverActiveRun(
  messages: ChatMessage[],
  approvals: Approval[],
  excludedRunIds: ReadonlySet<string> = new Set(),
): string | null {
  const pending = approvals.find((approval) =>
    messages.some((message) => message.run_id === approval.run_id),
  );
  if (pending && !excludedRunIds.has(pending.run_id)) return pending.run_id;
  const last = messages.at(-1);
  if (!last?.run_id) return null;
  if (last.role === "user" && !excludedRunIds.has(last.run_id)) return last.run_id;
  return null;
}
