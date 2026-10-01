const statusLabels: Record<string, string> = {
  open: "Mới tạo",
  in_progress: "Đang xử lý",
  resolved: "Đã giải quyết",
  healthy: "Hoạt động",
  degraded: "Gián đoạn nhẹ",
  down: "Không hoạt động",
  unknown: "Chưa xác định",
  published: "Published",
  draft: "Draft",
  ready: "Sẵn sàng",
  processing: "Đang xử lý",
  failed: "Thất bại",
  revoked: "Đã thu hồi",
  pending: "Chờ xác nhận",
  waiting_approval: "Chờ xác nhận",
  active: "Đang hoạt động",
  inactive: "Ngừng dùng",
  high: "Cao",
  normal: "Trung bình",
  low: "Thấp",
};

const issueLabels: Record<string, string> = {
  vpn: "VPN",
  docker: "Docker",
  gitlab: "GitLab",
  other: "Khác",
};

export function formatStatus(value: string): string {
  return statusLabels[value.toLowerCase()] ?? value.replaceAll("_", " ");
}

export function formatIssueType(value: string): string {
  return issueLabels[value.toLowerCase()] ?? value;
}

export function formatShortDate(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" }).format(
    date,
  );
}

export function formatDateTime(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatRelativeTime(value: string, now = new Date()): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  const deltaSeconds = Math.round((date.getTime() - now.getTime()) / 1_000);
  const formatter = new Intl.RelativeTimeFormat("vi", { numeric: "auto" });
  if (Math.abs(deltaSeconds) < 60) return formatter.format(deltaSeconds, "second");
  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (Math.abs(deltaMinutes) < 60) return formatter.format(deltaMinutes, "minute");
  const deltaHours = Math.round(deltaMinutes / 60);
  if (Math.abs(deltaHours) < 24) return formatter.format(deltaHours, "hour");
  const deltaDays = Math.round(deltaHours / 24);
  if (Math.abs(deltaDays) < 30) return formatter.format(deltaDays, "day");
  return formatDateTime(value);
}
