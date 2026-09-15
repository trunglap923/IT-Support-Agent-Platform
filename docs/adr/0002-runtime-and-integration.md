# ADR-0002 — Runtime foundation của WP-01

Ngày: 2026-09-15  
Trạng thái: chấp nhận cho WP-01; các spike MCP/LangGraph/checkpointer vẫn đang chờ M0.

## Bối cảnh

WP-01 cần một backend và frontend cài lại được từ lockfile, chạy không cần API trả phí và có cùng lệnh kiểm tra ở local/CI. Máy phát triển có Python 3.12, uv và Docker nhưng không có Node trên host.

## Quyết định

- Backend là package Python 3.12 cài bằng uv, dùng FastAPI app factory và tạo provider trong lifespan.
- Fake provider là mặc định. Chế độ OpenAI thiếu key dừng ngay khi nạp settings; import package không gọi mạng.
- OpenAI adapter ban đầu chỉ có plain text Responses call, đặt store=false, timeout 20 giây và tắt retry SDK. Tool/structured output, budget ledger và embedding thuộc WP sau.
- Frontend dùng Node 22.23.2, React/TypeScript/Vite, router, TanStack Query và Tailwind. Host thiếu Node có thể dùng image Node theo digest trong Makefile.
- CI tách backend/frontend và không có OpenAI/Langfuse secret.
- Starlette 1.6 test client dùng httpx2; dependency này được khai báo trực tiếp cho test để tránh fallback httpx cũ.

## Phiên bản đã khóa

| Thành phần | Phiên bản |
|---|---:|
| Python / uv | 3.12.3 / 0.11.32 |
| FastAPI / Starlette | 0.141.1 / 1.6.0 |
| Pydantic / settings | 2.13.5 / 2.15.0 |
| OpenAI Python SDK | 2.54.0 |
| httpx2 | 2.13.0 |
| Node | 22.23.2 |
| React / React Router | 19.3.0 / 7.18.3 |
| Vite / TypeScript | 7.3.6 / 5.9.3 |
| ESLint / Vitest | 10.10.0 / 4.1.11 |
| Tailwind CSS | 4.3.3 |

Hai lockfile mới là nguồn chính xác cho toàn bộ dependency bắc cầu.

## Bằng chứng

- Backend: Ruff format/lint, mypy strict và 6 pytest đạt.
- Frontend: npm ci báo 0 vulnerability tại thời điểm kiểm tra; ESLint, TypeScript, 1 Vitest và Vite production build đạt trong Node container.
- Uvicorn khởi động application lifecycle thành công ở fake mode.

GitHub Actions chưa thể chạy trước khi commit được push; lần CI remote đầu tiên vẫn là điều kiện xác nhận cuối.

## Hệ quả và phần hoãn

WP-01 chỉ tạo foundation. Không coi plain text provider là agent, không coi fake test là đánh giá model. Chưa cài LangGraph, MCP, PostgreSQL, Redis, Celery hoặc Langfuse cho tới khi WP tương ứng sử dụng chúng.

M0 còn phải thử Responses structured tools bằng account thật có quota, MCP stdio actor isolation và PostgreSQL checkpointer pause/resume; kết quả sẽ bổ sung hoặc thay thế ADR này nếu cần.
