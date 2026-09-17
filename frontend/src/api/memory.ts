export interface MemoryConsent {
  enabled: boolean;
  epoch: number;
}

export interface MemoryDevice {
  id: string;
  label: string;
  platform: "windows" | "macos" | "linux" | "other";
  active: boolean;
  version: number;
}

export interface MemoryCandidate {
  id: string;
  kind: "profile" | "preference" | "device";
  key: string;
  value: string;
  evidence: string;
  device_id: string | null;
  status: string;
  version: number;
  expires_at: string;
}

export interface MemoryFact {
  id: string;
  kind: string;
  key: string;
  value: string;
  scope: "global" | "device";
  device_id: string | null;
  version: number;
  expires_at: string;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  return requestJson(url, {
    ...init,
    messages: {
      fallback: "Không thể xử lý yêu cầu memory.",
      byStatus: { 409: "Memory đã thay đổi. Hãy tải lại và thử lại." },
    },
  });
}

function mutationHeaders(csrfToken: string) {
  return { "Content-Type": "application/json", "X-CSRF-Token": csrfToken };
}

export function getMemoryConsent(signal?: AbortSignal): Promise<MemoryConsent> {
  return request("/api/v1/memory/consent", { signal });
}

export function listMemoryDevices(signal?: AbortSignal): Promise<MemoryDevice[]> {
  return request("/api/v1/memory/devices", { signal });
}

export function listMemoryCandidates(signal?: AbortSignal): Promise<MemoryCandidate[]> {
  return request("/api/v1/memory/candidates", { signal });
}

export function listMemoryFacts(signal?: AbortSignal): Promise<MemoryFact[]> {
  return request("/api/v1/memory/facts", { signal });
}

export function setMemoryConsent(
  consent: MemoryConsent,
  enabled: boolean,
  csrfToken: string,
): Promise<MemoryConsent> {
  return request("/api/v1/memory/consent", {
    method: "PUT",
    headers: mutationHeaders(csrfToken),
    body: JSON.stringify({ enabled, expected_epoch: consent.epoch }),
  });
}

export function createMemoryDevice(
  label: string,
  platform: MemoryDevice["platform"],
  csrfToken: string,
): Promise<MemoryDevice> {
  return request("/api/v1/memory/devices", {
    method: "POST",
    headers: mutationHeaders(csrfToken),
    body: JSON.stringify({ label, platform }),
  });
}

export function confirmMemoryCandidate(
  candidate: MemoryCandidate,
  value: string,
  deviceId: string | null,
  csrfToken: string,
): Promise<MemoryFact> {
  return request(`/api/v1/memory/candidates/${encodeURIComponent(candidate.id)}/confirm`, {
    method: "POST",
    headers: mutationHeaders(csrfToken),
    body: JSON.stringify({
      expected_version: candidate.version,
      corrected_value: value,
      device_id: deviceId,
    }),
  });
}

export function rejectMemoryCandidate(
  candidate: MemoryCandidate,
  csrfToken: string,
): Promise<MemoryCandidate> {
  return request(`/api/v1/memory/candidates/${encodeURIComponent(candidate.id)}/reject`, {
    method: "POST",
    headers: mutationHeaders(csrfToken),
    body: JSON.stringify({ expected_version: candidate.version }),
  });
}

export function updateMemoryFact(
  fact: MemoryFact,
  value: string,
  csrfToken: string,
): Promise<MemoryFact> {
  return request(`/api/v1/memory/facts/${encodeURIComponent(fact.id)}`, {
    method: "PATCH",
    headers: mutationHeaders(csrfToken),
    body: JSON.stringify({ expected_version: fact.version, value }),
  });
}

export async function deleteMemoryFact(
  fact: MemoryFact,
  csrfToken: string,
): Promise<void> {
  return requestJson<void>(
    `/api/v1/memory/facts/${encodeURIComponent(fact.id)}?expected_version=${fact.version}`,
    {
      method: "DELETE",
      headers: { "X-CSRF-Token": csrfToken },
      messages: { fallback: "Không thể xóa memory. Hãy tải lại và thử lại." },
    },
  );
}
import { requestJson } from "./client";
