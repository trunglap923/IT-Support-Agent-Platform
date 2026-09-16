# IT Support Agent Platform

Portfolio trợ lý IT: trả lời có nguồn, kiểm tra dịch vụ mô phỏng, tạo ticket có xác nhận và nhớ thông tin đã được người dùng đồng ý lưu.

## Trạng thái hiện tại

Đã khởi tạo cây thư mục và **57 kế hoạch module**. Mỗi `PLAN.md` có phạm vi, hợp đồng, tệp cần viết, phần phụ thuộc, checklist có mã và điều kiện hoàn thành.

WP-01, compatibility M0, WP-02 và WP-03 đã hoàn thành ở local. WP-02 gồm
PostgreSQL/pgvector, Alembic, Argon2, session-cookie, CSRF/RBAC, conversation/run
persistence và login UI. Gate WP-02 đạt 9 PostgreSQL integration tests, bao gồm
regression vô hiệu hóa tài khoản khi session cũ vẫn còn hạn.

WP-03 bổ sung Redis AOF/noeviction, Celery agent/background workers, durable run state và
event store, commit-then-enqueue/reconcile, owner-scoped SSE cùng màn hình theo dõi run có
bounded reconnect. Kết quả ngày 2026-09-16: Ruff/mypy đạt, 14 unit tests WP-03 và 5
PostgreSQL/Redis integration tests đạt; frontend lint/typecheck, 9 tests và production
build đạt. Dataset M0 có 30/30 case hợp lệ và Responses live đạt cả ba contract. Workflow
GitHub Actions chưa được chạy theo yêu cầu hiện tại.

## Chạy development

Yêu cầu: Python 3.12, uv 0.11.x và Docker; hoặc Node 22.23.2 + npm trên host.

PostgreSQL development dùng image PostgreSQL 17 + pgvector đã pin digest, chỉ publish
trên loopback. Nếu `.env` được tạo trước WP-02, bổ sung các biến `POSTGRES_*`,
`DATABASE_URL` và `MIGRATION_DATABASE_URL` từ `.env.example`, rồi chạy:

~~~bash
make db-up
make redis-up
make db-status
make migrate
make seed-demo-user
~~~

`make db-down` và `make redis-down` chỉ dừng service tương ứng và giữ named volume;
`make services-up`/`make services-down` quản lý cả hai service. Redis chỉ publish trên
loopback, bật AOF `everysec` và `noeviction` để không âm thầm loại queue key.
Không dùng password development cho môi trường khác và không commit `.env`.

Alembic dùng riêng `MIGRATION_DATABASE_URL` với driver `postgresql+psycopg`; ứng dụng dùng
`DATABASE_URL` với `postgresql+asyncpg`. Migration test tạo và xóa một database cô lập,
không reset database development đang dùng.

Demo identity tối thiểu dùng email `employee.engineering@example.com`. Lệnh seed đọc
password từ `DEMO_SEED_PASSWORD`, lưu Argon2 hash và không ghi password vào source/log.
Chạy lại lệnh không nhân đôi user.

Sau khi migrate và seed, mở http://127.0.0.1:5173 rồi đăng nhập bằng email trên và đúng
password bạn đã đặt ở `DEMO_SEED_PASSWORD`. Trình duyệt phải dùng đúng host
`127.0.0.1` để khớp `ALLOWED_WEB_ORIGIN`; nếu đổi host/cổng, cập nhật biến đó.

~~~bash
cp .env.example .env
make backend-sync
make backend-check
make frontend-check-docker
make wp03-integration-check
~~~

`wp02-integration-check` và `wp03-integration-check` tạo database PostgreSQL tạm có tên
ngẫu nhiên rồi xóa sau test. WP-03 dùng `TEST_REDIS_URL` ở database 15 và chỉ cleanup
queue test; các lệnh không migrate/reset database demo. `backend-integration-check` chạy
cả hai nhóm. Chạy `make wp02-check` hoặc `make wp03-check` khi các service tương ứng đã
healthy.

Celery có hai worker riêng và một beat scheduler. Sau `make services-up`, có thể mở ba
terminal khác nhau để chạy `make worker-agent`, `make worker-background` và
`make scheduler`. Chỉ chạy một scheduler cho một environment; queue payload chỉ chứa ID,
còn PostgreSQL là nguồn trạng thái.

Sau khi đăng nhập, route `/chat?run_id=<UUID>` hiển thị snapshot và event SSE của một run
đã tồn tại. UI tạo conversation/message và final answer sẽ được nối ở WP-06; màn hình
WP-03 hiện chỉ kiểm chứng luồng theo dõi/reconnect, không tự tạo run mới.

Chạy hai terminal để xem giao diện. Backend development bind vào `0.0.0.0` để
frontend trong Docker có thể gọi API qua Docker host gateway; frontend chỉ được
publish trên loopback của máy ở cổng `5173`.

~~~bash
# Terminal 1
make dev-backend

# Terminal 2
make dev-frontend-docker
~~~

Mở http://127.0.0.1:5173. Health API ở http://127.0.0.1:8000/api/v1/health/live. Chế độ mặc định dùng fake provider và không gọi OpenAI.

Nếu host đã có đúng Node/npm, thay hai target Docker bằng `make frontend-install`, `make frontend-check` và `make dev-frontend`.

Nhấn `Ctrl+C` trong từng terminal để dừng tiến trình. Frontend container có tên
cố định `it-support-agent-frontend-dev`, dùng `--rm` và thường tự xóa sau khi
dừng. Nếu terminal đóng bất thường hoặc lần chạy sau báo container cũ, dọn đúng
container development bằng:

~~~bash
make dev-stop
~~~

`make dev-stop` chỉ dừng/xóa frontend container do dự án quản lý; backend chạy
trực tiếp trên host vẫn được dừng bằng `Ctrl+C`. Nếu cổng `5173` thuộc về một
container khác, xác định nó trước khi dừng:

~~~bash
docker ps --filter publish=5173
~~~

Có thể đổi cổng frontend cho một lần chạy mà không dừng dự án khác:

~~~bash
make dev-frontend-docker FRONTEND_DEV_PORT=5174
~~~

## Kiểm chứng compatibility M0

Các kiểm tra không trả phí:

~~~bash
make spike-mcp-stdio
make eval-validate
CHECKPOINT_DATABASE_URL=postgresql://... make spike-langgraph-postgres
~~~

Responses live là lệnh riêng có thể phát sinh phí, không chạy trong CI và chỉ hoạt động khi
đồng thời có `OPENAI_API_KEY` trong `.env` và opt-in rõ ràng:

~~~bash
RUN_OPENAI_LIVE_SPIKE=1 make spike-openai-live
~~~

Kết quả/phiên bản chi tiết nằm trong [ADR-0002](docs/adr/0002-runtime-and-integration.md).

## Bắt đầu từ đâu?

1. Đọc [kế hoạch tổng](plan.md) để nắm phạm vi V1 và quy tắc nghiệp vụ.
2. Mở [roadmap và mục lục kế hoạch module](docs/implementation-roadmap.md); bắt đầu WP-01.
3. Đọc `PLAN.md` của module sắp làm, tạo code cùng kiểm thử và chỉ đánh dấu hoàn thành khi đạt điều kiện trong file.
4. Nếu thay đổi thiết kế, cập nhật [ADR](docs/adr/PLAN.md), kế hoạch tổng và các module bị ảnh hưởng.

Ưu tiên WP-01 → WP-06 để có demo chat/RAG sớm; sau đó triển khai MCP, approval/ticket, recovery, document admin và memory theo phụ thuộc. Không cần viết đồng thời mọi thư mục.

## Cấu trúc chính

```text
backend/
  app/
    api/ auth/
    agent/context/
    rag/{ingestion,chunking,retrieval,citations}/
    memory/ tools/ mcp_server/
    services/{conversations,approvals,tickets,documents,budget,service_status}/
    repositories/ db/ providers/ jobs/ observability/ prompts/
  migrations/
  tests/{unit,integration,contract}/
frontend/
  src/
    api/ components/
    features/{auth,chat,tickets,documents,memory,services}/
  e2e/
data/{seed,knowledge,manifests}/
evals/{cases,rubrics,runner}/
reports/
docs/adr/
docs/archive/plan-original.md
infra/
.github/workflows/
```

Ký hiệu `{...}` trong cây rút gọn đại diện cho các thư mục con riêng. Mọi module nêu trên có `PLAN.md`; tài liệu archive được giữ nguyên.

| Khu vực | Kế hoạch đầu vào |
|---|---|
| Backend/API/agent | [backend/PLAN.md](backend/PLAN.md) |
| Frontend | [frontend/PLAN.md](frontend/PLAN.md) |
| Dữ liệu demo | [data/PLAN.md](data/PLAN.md) |
| Evaluation | [evals/PLAN.md](evals/PLAN.md) |
| Báo cáo | [reports/PLAN.md](reports/PLAN.md) |
| Vận hành local | [infra/PLAN.md](infra/PLAN.md) |
| CI | [.github/workflows/PLAN.md](.github/workflows/PLAN.md) |

## Quy ước và cấu hình

- Định hướng stack: Python/FastAPI, React/TypeScript, PostgreSQL/pgvector, LangGraph, MCP, Celery/Redis và Langfuse. Backend/frontend foundation, MCP SDK và LangGraph checkpointer compatibility đã được khóa; implementation nghiệp vụ vẫn theo các WP trong roadmap.
- [.env.example](.env.example) là mẫu không có secret. `AI_PROVIDER=fake` là mặc định; `AI_PROVIDER=openai` yêu cầu `OPENAI_API_KEY`. Không gửi API key vào chat hoặc commit vào repo.
- [.python-version](.python-version), [.editorconfig](.editorconfig) và [.gitignore](.gitignore) thống nhất phiên bản Python dự kiến, định dạng và dữ liệu không commit.
- Makefile cung cấp lệnh WP-01, compatibility spikes và validation 30 case M0. `make up`, migrations, seed, E2E và live evaluation runner sẽ được thêm ở các WP tương ứng.
- Dữ liệu mẫu phải là dữ liệu tự tạo/công khai có quyền sử dụng. Không kết nối VPN/GitLab/ticketing của doanh nghiệp thật trong V1.

Xem [bản đồ kiến trúc](docs/architecture.md) và [kịch bản demo dự kiến](docs/demo-script.md). Chỉ báo cáo metric và tính năng đã chạy kiểm chứng.
