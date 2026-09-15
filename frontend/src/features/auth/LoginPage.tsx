import type { FormEvent } from "react";
import { Link } from "react-router-dom";

export function LoginPage() {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
          <li>Memory tắt mặc định và cần sự đồng ý</li>
        </ul>
      </section>

      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">DEMO ACCESS</p>
        <h2 id="login-title">Đăng nhập</h2>
        <p>Form đã sẵn sàng cho API session ở WP-02.</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="email">Email</label>
          <input
            autoComplete="username"
            id="email"
            name="email"
            placeholder="employee.engineering@example.com"
            type="email"
          />
          <label htmlFor="password">Mật khẩu</label>
          <input
            autoComplete="current-password"
            id="password"
            name="password"
            placeholder="••••••••"
            type="password"
          />
          <button disabled type="submit">
            Sẽ kết nối ở WP-02
          </button>
        </form>
        <Link className="back-link" to="/">
          ← Xem trạng thái hệ thống
        </Link>
      </section>
    </main>
  );
}
