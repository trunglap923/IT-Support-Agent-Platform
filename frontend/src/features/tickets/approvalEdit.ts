import type { TicketDraftArguments } from "../../api/tickets";

export function formatTicketDraftForChat(values: TicketDraftArguments): string {
  const lines = [
    "Tạo ticket hỗ trợ với thông tin sau:",
    `Tiêu đề: ${values.title}`,
    `Mô tả: ${values.description}`,
    `Loại sự cố: ${values.issue_type}`,
    `Mức độ: ${values.severity}`,
  ];
  if (values.device_id) lines.push(`Thiết bị: ${values.device_id}`);
  return lines.join("\n");
}
