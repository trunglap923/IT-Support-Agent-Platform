import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  Clock3,
  Container,
  GitBranch,
  ShieldCheck,
  TicketCheck,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getDashboard, type DashboardData } from "../api/dashboard";
import {
  EmptyState,
  LoadingState,
  MetricCard,
  PageHeader,
  SectionHeader,
  StatusBadge,
} from "../components/ProductUI";
import { formatIssueType, formatRelativeTime, formatShortDate } from "../utils/format";
import { useAuth } from "./auth/useAuth";

const chartColors: Record<string, string> = {
  gitlab: "#2f6fe4",
  vpn: "#28b779",
  docker: "#f2b33d",
  other: "#94a3b8",
};

const activityLabels: Record<string, string> = {
  "ticket.created": "đã tạo ticket",
  "ticket.in_progress": "đã bắt đầu xử lý",
  "ticket.resolved": "đã giải quyết",
  "ticket.open": "đã mở lại ticket",
};

function Comparison({ value, label }: { value: number | null; label: string }) {
  if (value === null) return <span className="metric-current">Dữ liệu hiện tại</span>;
  const direction = value > 0 ? "up" : value < 0 ? "down" : "flat";
  return (
    <span className={`metric-comparison ${direction}`}>
      {value > 0 ? "+" : ""}{value} {label}
    </span>
  );
}

function ServiceIcon({ serviceId }: { serviceId: string }) {
  if (serviceId === "gitlab") return <GitBranch aria-hidden="true" />;
  if (serviceId === "registry") return <Container aria-hidden="true" />;
  return <ShieldCheck aria-hidden="true" />;
}

export function DashboardPage() {
  const { user } = useAuth();
  const [rangeDays, setRangeDays] = useState<7 | 30>(7);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void getDashboard(rangeDays, controller.signal)
      .then(setData)
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof Error ? caught.message : "Không thể tải dữ liệu tổng quan.");
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [rangeDays]);

  const chartData = useMemo(() => data?.daily_activity.map((point) => ({
    ...point,
    label: formatShortDate(point.date),
  })) ?? [], [data]);
  const totalTickets = data?.issue_distribution.reduce((sum, item) => sum + item.count, 0) ?? 0;

  if (loading && !data) return <LoadingState label="Đang tổng hợp dữ liệu vận hành…" />;

  return (
    <div className="dashboard-page">
      <PageHeader
        title="Tổng quan"
        description={`Theo dõi hoạt động IT Support của ${user?.display_name ?? "workspace"} bằng dữ liệu theo phạm vi truy cập.`}
        actions={(
          <label className="compact-select">
            <Clock3 aria-hidden="true" size={16} />
            <span className="sr-only">Khoảng thời gian</span>
            <select value={rangeDays} onChange={(event) => {
              setLoading(true);
              setError(null);
              setRangeDays(Number(event.target.value) as 7 | 30);
            }}>
              <option value={7}>7 ngày qua</option>
              <option value={30}>30 ngày qua</option>
            </select>
          </label>
        )}
      />

      {error ? <div className="alert-banner error" role="alert">{error}</div> : null}

      <section className="metric-grid" aria-label="Chỉ số vận hành">
        <MetricCard label="Ticket đang mở" value={data?.metrics.open ?? "—"} icon={TicketCheck} detail={<span className="metric-current">Dữ liệu hiện tại</span>} />
        <MetricCard label="Đang xử lý" value={data?.metrics.in_progress ?? "—"} icon={Activity} tone="amber" detail={<span className="metric-current">Dữ liệu hiện tại</span>} />
        <MetricCard label="Ưu tiên cao" value={data?.metrics.high_priority_unresolved ?? "—"} icon={AlertTriangle} tone="red" detail={<span className="metric-current">Cần chú ý sớm</span>} />
        <MetricCard label="Đã giải quyết" value={data?.metrics.resolved_in_range ?? "—"} icon={CheckCircle2} tone="green" detail={<Comparison value={data?.comparison.resolved_in_range ?? null} label="so với kỳ trước" />} />
      </section>

      <div className="dashboard-grid">
        <section className="panel chart-panel dashboard-trend">
          <SectionHeader title="Xu hướng ticket" description={`Hoạt động trong ${rangeDays} ngày gần nhất.`} />
          {chartData.some((point) => point.created + point.started + point.resolved > 0) ? (
            <div className="chart-body" aria-label="Biểu đồ ticket tạo mới, bắt đầu xử lý và đã giải quyết">
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={chartData} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="#e8edf4" vertical={false} />
                  <XAxis axisLine={false} dataKey="label" fontSize={11} tickLine={false} />
                  <YAxis allowDecimals={false} axisLine={false} fontSize={11} tickLine={false} />
                  <Tooltip cursor={{ fill: "#f5f8fc" }} />
                  <Legend iconType="circle" iconSize={8} />
                  <Bar dataKey="created" fill="#2f6fe4" name="Mới tạo" radius={[3, 3, 0, 0]} stackId="tickets" />
                  <Bar dataKey="started" fill="#79a9f4" name="Bắt đầu xử lý" stackId="tickets" />
                  <Bar dataKey="resolved" fill="#35bf82" name="Đã giải quyết" radius={[3, 3, 0, 0]} stackId="tickets" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyState title="Chưa có hoạt động trong kỳ" description="Biểu đồ sẽ xuất hiện khi có ticket mới hoặc thay đổi trạng thái." />}
        </section>

        <section className="panel dashboard-services">
          <SectionHeader title="Trạng thái hệ thống" description="Trạng thái mô phỏng hiện tại." />
          <div className="service-status-list">
            {data?.services.map((service) => (
              <article key={service.service_id}>
                <span className={`service-state-dot ${service.status}`} />
                <span className="service-status-icon"><ServiceIcon serviceId={service.service_id} /></span>
                <span><strong>{service.service_id === "registry" ? "Docker Registry" : service.service_id === "gitlab" ? "GitLab" : "VPN Gateway"}</strong><small>{service.message}</small></span>
                <StatusBadge value={service.status} />
              </article>
            ))}
            {!data?.services.length ? <EmptyState title="Chưa có trạng thái dịch vụ" description="Dữ liệu dịch vụ sẽ xuất hiện tại đây." /> : null}
          </div>
        </section>

        <section className="panel dashboard-attention">
          <SectionHeader title="Cần chú ý" description="Ticket chưa hoàn tất, ưu tiên theo mức độ và thời gian mở." actions={<Link className="text-link" to="/tickets">Xem tất cả</Link>} />
          {!data?.attention_tickets.length ? <EmptyState title="Không có ticket tồn đọng" description="Các ticket mới cần xử lý sẽ xuất hiện tại đây." /> : (
            <div className="table-scroll">
              <table className="data-table attention-table">
                <thead><tr><th>Mã ticket</th><th>Tiêu đề</th><th>Dịch vụ</th><th>Mức độ</th><th>Cập nhật</th><th>Trạng thái</th></tr></thead>
                <tbody>{data.attention_tickets.map((ticket) => (
                  <tr key={ticket.id}>
                    <td><Link className="table-key" to={`/tickets/${ticket.id}`}>{ticket.display_key}</Link></td>
                    <td><strong>{ticket.title}</strong><small>{ticket.requester_name}</small></td>
                    <td>{formatIssueType(ticket.issue_type)}</td>
                    <td><StatusBadge value={ticket.severity} /></td>
                    <td>{formatRelativeTime(ticket.updated_at)}</td>
                    <td><StatusBadge value={ticket.status} /></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </section>

        <section className="panel dashboard-activity">
          <SectionHeader title="Hoạt động gần đây" description="Theo phạm vi bạn được phép xem." />
          <ul className="activity-list">
            {data?.recent_activity.map((item) => (
              <li key={item.id}>
                <span className="activity-list-icon"><CircleDot aria-hidden="true" size={16} /></span>
                <span><strong>{item.actor_name ?? "Hệ thống"} {activityLabels[item.event_type] ?? "đã cập nhật"}</strong><small>{item.display_key} · {item.title}</small></span>
                <time dateTime={item.occurred_at}>{formatRelativeTime(item.occurred_at)}</time>
              </li>
            ))}
            {!data?.recent_activity.length ? <li className="activity-empty">Chưa có hoạt động gần đây.</li> : null}
          </ul>
        </section>

        <section className="panel dashboard-distribution">
          <SectionHeader title="Phân loại ticket" description="Phân bổ theo dịch vụ hiện tại." />
          <div className="distribution-layout">
            <div className="donut-wrap" aria-label={`Tổng ${totalTickets} ticket`}>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={data?.issue_distribution ?? []} dataKey="count" nameKey="issue_type" innerRadius={58} outerRadius={84} paddingAngle={2}>
                    {(data?.issue_distribution ?? []).map((item) => <Cell fill={chartColors[item.issue_type] ?? chartColors.other} key={item.issue_type} />)}
                  </Pie>
                  <Tooltip formatter={(value, name) => [value, formatIssueType(String(name))]} />
                </PieChart>
              </ResponsiveContainer>
              <span><strong>{totalTickets}</strong><small>Tổng ticket</small></span>
            </div>
            <ul className="distribution-legend">
              {data?.issue_distribution.map((item) => (
                <li key={item.issue_type}><i style={{ background: chartColors[item.issue_type] ?? chartColors.other }} /><span>{formatIssueType(item.issue_type)}</span><strong>{item.count} {totalTickets ? `(${Math.round(item.count / totalTickets * 100)}%)` : ""}</strong></li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </div>
  );
}
