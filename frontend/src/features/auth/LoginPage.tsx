import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { BookOpenCheck, Brain, ShieldCheck } from "lucide-react";

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
    <main className="auth-page">
      <section className="auth-context" aria-label="Giới thiệu hệ thống">
        <div className="auth-brand">
          <span className="brand-mark">IT</span>
          <span><strong>Support Agent</strong><small>Engineering workspace</small></span>
        </div>
        <div className="auth-summary">
          <p className="eyebrow">INTERNAL SUPPORT WORKSPACE</p>
          <h1>Giải quyết yêu cầu IT với đúng ngữ cảnh.</h1>
          <p>Tra cứu hướng dẫn nội bộ, theo dõi ticket và làm việc với trợ lý AI trong một không gian có kiểm soát.</p>
        </div>
        <ul className="auth-assurances">
          <li><span><BookOpenCheck aria-hidden="true" size={18} /></span><div><strong>Câu trả lời có nguồn</strong><small>Citation được xác thực trước khi hiển thị.</small></div></li>
          <li><span><ShieldCheck aria-hidden="true" size={18} /></span><div><strong>Hành động cần xác nhận</strong><small>Ticket không được tạo trước khi bạn duyệt.</small></div></li>
          <li><span><Brain aria-hidden="true" size={18} /></span><div><strong>Memory minh bạch</strong><small>Chỉ fact đã xác nhận mới được sử dụng.</small></div></li>
        </ul>
      </section>

      <section className="login-card" aria-labelledby="login-title">
        <div className="login-card-heading">
          <p className="eyebrow">SECURE ACCESS</p>
          <h2 id="login-title">Đăng nhập</h2>
          <p>Sử dụng tài khoản workspace của bạn để tiếp tục.</p>
        </div>
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
        <div className="login-footnote">
          <span className="environment-indicator"><i /> Demo environment</span>
          <small>Phiên đăng nhập được bảo vệ bằng cookie HttpOnly.</small>
        </div>
      </section>
    </main>
  );
}
