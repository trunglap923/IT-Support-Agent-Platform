import { requestJson } from "./client";

export interface DashboardMetrics {
  open: number;
  in_progress: number;
  high_priority_unresolved: number;
  resolved_in_range: number;
  pending_approvals: number;
}

export interface DashboardComparison {
  resolved_in_range: number | null;
  created_in_range: number | null;
}

export interface DailyActivityPoint {
  date: string;
  created: number;
  started: number;
  resolved: number;
}

export interface IssueDistributionItem {
  issue_type: string;
  count: number;
}

export interface DashboardActivityItem {
  id: string;
  event_type: string;
  occurred_at: string;
  ticket_id: string;
  display_key: string;
  title: string;
  actor_name: string | null;
}

export interface DashboardTicketItem {
  id: string;
  display_key: string;
  title: string;
  issue_type: string;
  severity: string;
  status: string;
  requester_name: string;
  created_at: string;
  updated_at: string;
}

export interface DashboardServiceItem {
  service_id: string;
  status: string;
  message: string;
  updated_at: string;
}

export interface DashboardData {
  range_days: number;
  generated_at: string;
  scope: "personal" | "department" | "global";
  metrics: DashboardMetrics;
  comparison: DashboardComparison;
  daily_activity: DailyActivityPoint[];
  issue_distribution: IssueDistributionItem[];
  recent_activity: DashboardActivityItem[];
  attention_tickets: DashboardTicketItem[];
  services: DashboardServiceItem[];
}

export function getDashboard(
  rangeDays: 7 | 30,
  signal?: AbortSignal,
): Promise<DashboardData> {
  return requestJson(`/api/v1/dashboard?range_days=${rangeDays}`, {
    signal,
    messages: { fallback: "Không thể tải dữ liệu tổng quan." },
  });
}
