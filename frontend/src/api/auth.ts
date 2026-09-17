export type UserRole = "employee" | "it" | "admin";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  department_id: string;
  department_key: string;
}

export interface CurrentSession {
  user: AuthUser;
  csrf_token: string;
}

export interface LoginResult extends CurrentSession {
  expires_at: string;
}

export async function login(email: string, password: string): Promise<LoginResult> {
  return requestJson<LoginResult>("/api/v1/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
    notifyOnUnauthorized: false,
    messages: {
      byStatus: {
        401: "Email hoặc mật khẩu không đúng.",
        403: "Yêu cầu bảo mật không hợp lệ. Hãy tải lại trang.",
        429: "Bạn đã thử đăng nhập quá nhiều lần. Vui lòng chờ rồi thử lại.",
      },
    },
  });
}

export async function getCurrentSession(signal?: AbortSignal): Promise<CurrentSession> {
  return requestJson<CurrentSession>("/api/v1/auth/me", {
    signal,
    notifyOnUnauthorized: false,
  });
}

export async function logout(csrfToken: string): Promise<void> {
  return requestJson<void>("/api/v1/auth/logout", {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    notifyOnUnauthorized: false,
  });
}
import { requestJson } from "./client";

export { ApiError } from "./client";
