export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  provider: string;
  request_id: string;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/v1/health/live", {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error("Không thể kết nối tới API.");
  }

  return (await response.json()) as HealthResponse;
}
