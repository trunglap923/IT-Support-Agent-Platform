export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  provider: string;
  request_id: string;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/v1/health/live", {
    signal,
    notifyOnUnauthorized: false,
    messages: { fallback: "Không thể kết nối tới API." },
  });
}
import { requestJson } from "./client";
