import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "./useAuth";

export function LoginPage() {
  const { user, isLoading: isBootstrapping, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const form = new FormData(event.currentTarget);
    try {
      await login(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
      const destination = (location.state as { from?: string } | null)?.from ?? "/";
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Đăng nhập không thành công.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isBootstrapping && user) {
    return <Navigate replace to="/" />;
  }

  return (
    <main className="login-page">
      <section className="login-copy">
        <Link className="brand" to="/">
          <span className="brand-mark">IT</span>
          <strong>Support Agent</strong>
        </Link>
        <p className="eyebrow">PORTFOLIO PROJECT</p>
        <h1>Hỗ trợ IT có nguồn, có kiểm soát.</h1>
        <p>
          Hỏi đáp tài liệu nội bộ, kiểm tra dịch vụ mô phỏng và tạo ticket sau khi
          người dùng xác nhận.
        </p>
        <ul>
          <li>Citation được kiểm tra ở backend</li>
          <li>Ticket không được tạo trước approval</li>
          <li>Memory luôn hoạt động nhưng chỉ dùng fact bạn đã xác nhận</li>
        </ul>
      </section>

      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">DEMO ACCESS</p>
        <h2 id="login-title">Đăng nhập</h2>
        <p>Dùng tài khoản demo đã được seed trong PostgreSQL.</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input
            autoComplete="username"
            id="email"
            name="email"
            placeholder="employee.engineering@example.com"
            required
            type="email"
          />
          <label htmlFor="password">Mật khẩu</label>
          <input
            autoComplete="current-password"
            id="password"
            name="password"
            placeholder="••••••••"
            required
            type="password"
          />
          {error ? <p className="form-error" role="alert">{error}</p> : null}
          <button disabled={isSubmitting || isBootstrapping} type="submit">
            {isSubmitting ? "Đang đăng nhập…" : "Đăng nhập"}
          </button>
        </form>
        <Link className="back-link" to="/">
          ← Xem trạng thái hệ thống
        </Link>
      </section>
    </main>
  );
}
