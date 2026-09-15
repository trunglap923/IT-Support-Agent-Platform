# ADR-0002 — Runtime foundation của WP-01

Ngày: 2026-09-15  
Trạng thái: chấp nhận cho WP-01; live Responses và LangGraph/checkpointer vẫn đang chờ M0.

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

### Spike Responses API

Ngày 2026-09-15, contract offline đã kiểm chứng với OpenAI Python SDK 2.54.0:

- plain text dùng `responses.create`;
- typed output dùng `responses.parse(..., text_format=<Pydantic model>)`;
- function tool dùng schema strict, `additionalProperties=false`, một tool call và giữ
  `call_id` để orchestration sử dụng ở bước tiếp theo;
- cả ba request đặt `store=false`, timeout SDK 20 giây, không retry và tổng trần output
  là 160 token.

`make spike-openai-live` là lệnh riêng, yêu cầu đồng thời API key và
`RUN_OPENAI_LIVE_SPIKE=1`. CI không gọi target này. Live model/account access chưa chạy,
vì chưa có opt-in trả phí trong bằng chứng của ADR; do đó chưa đánh dấu điều kiện live M0.

Tài liệu contract được đối chiếu với [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[Function Calling](https://developers.openai.com/api/docs/guides/function-calling) và
[GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) chính thức.

M0 còn phải chạy live Responses bằng account có quota và PostgreSQL checkpointer
pause/resume; kết quả sẽ bổ sung hoặc thay thế ADR này nếu cần.

### Spike MCP stdio và actor isolation

Ngày 2026-09-15, MCP Python SDK 2.2.0 đã được khóa và chạy kiểm chứng bằng transport
stdio thật. Client chính thức khởi động hai server subprocess đồng thời, discovery đúng
tool `current_actor`, gọi tool và nhận structured content đúng actor/run của từng process.

Mỗi subprocess nhận environment allowlist chỉ gồm actor, run và cấu hình Python I/O.
Contract test đặt OpenAI/Langfuse secrets giả ở process cha và xác nhận chúng không truyền
sang server. Kết quả chứng minh boundary subprocess; nó không thay thế session auth,
database ownership recheck hoặc ba business tools sẽ viết ở WP-07.

API được đối chiếu với [MCP Python SDK chính thức](https://github.com/modelcontextprotocol/python-sdk)
và tài liệu [stdio client/discovery/call](https://py.sdk.modelcontextprotocol.io/client/).
