import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="route-fallback">
      <p className="eyebrow">404</p>
      <h1>Không tìm thấy trang</h1>
      <p>Đường dẫn không tồn tại hoặc chưa được cung cấp trong bản demo này.</p>
      <Link className="primary-button" to="/">
        Về trang tổng quan
      </Link>
    </main>
  );
}
