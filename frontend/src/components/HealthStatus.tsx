import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../api/health";

export function HealthStatus() {
  const health = useQuery({
    queryKey: ["health", "live"],
    queryFn: ({ signal }) => getHealth(signal),
    retry: 1,
  });

  if (health.isPending) {
    return (
      <div className="status-card neutral" role="status">
        <span className="status-dot" />
        Đang kiểm tra API…
      </div>
    );
  }

  if (health.isError) {
    return (
      <div className="status-card error" role="alert">
        <span className="status-dot" />
        API chưa chạy. Khởi động backend để kiểm tra kết nối.
      </div>
    );
  }

  return (
    <div className="status-card success" role="status">
      <span className="status-dot" />
      API hoạt động · {health.data.environment} · provider {health.data.provider}
    </div>
  );
}
