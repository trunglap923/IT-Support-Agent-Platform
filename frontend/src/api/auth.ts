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

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function parseError(response: Response): Promise<ApiError> {
  if (response.status === 401) {
    return new ApiError("Email hoặc mật khẩu không đúng.", response.status);
  }
  if (response.status === 403) {
    return new ApiError("Yêu cầu bảo mật không hợp lệ. Hãy tải lại trang.", response.status);
  }
  if (response.status === 429) {
    return new ApiError(
      "Bạn đã thử đăng nhập quá nhiều lần. Vui lòng chờ rồi thử lại.",
      response.status,
    );
  }
  return new ApiError("Không thể kết nối tới máy chủ.", response.status);
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as LoginResult;
}

export async function getCurrentSession(signal?: AbortSignal): Promise<CurrentSession> {
  const response = await fetch("/api/v1/auth/me", {
    credentials: "same-origin",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as CurrentSession;
}

export async function logout(csrfToken: string): Promise<void> {
  const response = await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "X-CSRF-Token": csrfToken,
    },
  });
  if (!response.ok && response.status !== 401) {
    throw await parseError(response);
  }
}
