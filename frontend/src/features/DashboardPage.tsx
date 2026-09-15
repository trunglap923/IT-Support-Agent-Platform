import { Link } from "react-router-dom";

import { HealthStatus } from "../components/HealthStatus";

const capabilities = [
  {
    step: "01",
    title: "Hỏi có nguồn",
    description: "Tra cứu runbook VPN, Docker và GitLab với citation hợp lệ.",
  },
  {
    step: "02",
    title: "Xác nhận hành động",
    description: "Xem trước nội dung trước khi agent tạo ticket.",
  },
  {
    step: "03",
    title: "Nhớ có đồng ý",
    description: "Memory theo người dùng và thiết bị, tắt mặc định.",
  },
];

export function DashboardPage() {
  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">WP-01 · FOUNDATION</p>
          <h1>Một nơi để xử lý những vướng mắc IT thường ngày.</h1>
          <p className="hero-copy">
            Nền tảng đang ở bước khởi tạo. API health và giao diện shell đã chạy;
            các luồng chat, ticket và tài liệu sẽ được thêm theo roadmap.
          </p>
          <div className="hero-actions">
            <Link className="primary-button" to="/chat">
              Mở khu vực chat
            </Link>
            <Link className="secondary-button" to="/login">
              Xem màn hình đăng nhập
            </Link>
          </div>
        </div>
        <div className="health-panel">
          <p className="panel-label">SYSTEM CHECK</p>
          <HealthStatus />
          <dl>
            <div>
              <dt>Backend</dt>
              <dd>FastAPI · Python 3.12</dd>
            </div>
            <div>
              <dt>Frontend</dt>
              <dd>React · TypeScript</dd>
            </div>
            <div>
              <dt>Chế độ mặc định</dt>
              <dd>Fake provider · không tốn API</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="capabilities" aria-labelledby="capabilities-title">
        <div className="section-heading">
          <p className="eyebrow">ROADMAP</p>
          <h2 id="capabilities-title">Ba nguyên tắc xuyên suốt</h2>
        </div>
        <div className="capability-grid">
          {capabilities.map((capability) => (
            <article key={capability.step}>
              <span>{capability.step}</span>
              <h3>{capability.title}</h3>
              <p>{capability.description}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
