# IT Support Agent Platform

Portfolio prototype cho trợ lý IT có trạng thái: chat RAG kèm nguồn, service status mô phỏng, ticket cần phê duyệt, memory có consent và quản trị tài liệu có version/ACL.

## Trạng thái

Ứng dụng và local stack đã triển khai qua WP-01–WP-14. Bằng chứng local ngày 2026-09-16:

- stack Compose 7/7 service healthy trên project sạch;
- backend `113 passed, 1 skipped`; frontend lint/typecheck, `15 passed`, production build;
- Playwright `7 passed`; contract `7 passed`; evaluation schema 120 case và reproducibility 160 runs;
- backup PostgreSQL/document storage restore thành công vào database và volume tạm;
- G-01–G-04 pass; G-05–G-09 vẫn `not_measured`, nên release decision là **not ready**.

GitHub Actions đã được cấu hình nhưng chưa có bằng chứng remote run sau push. Fake mode chứng minh contract/wiring, không chứng minh chất lượng semantic của model thật.

## Kiến trúc

```text
Browser → Nginx/React → FastAPI → PostgreSQL/pgvector
                              ↘ Redis → Celery agent/background + scheduler
Agent worker → LangGraph → scoped RAG / governed tools → MCP stdio → business services
                         ↘ fake hoặc OpenAI provider → optional Langfuse
```

PostgreSQL là nguồn trạng thái bền vững. Redis là broker/rate-limit/cache; side effect ticket được bảo vệ bởi approval, idempotency receipt và reconciliation. Xem [bản đồ kiến trúc](docs/architecture.md) và [ADR runtime](docs/adr/0002-runtime-and-integration.md).

## Quick start bằng Docker

Yêu cầu: Docker Engine có Compose plugin và GNU Make. Không cần cài Python/Node trên host.

```bash
cp .env.example .env
```

Sửa ít nhất hai giá trị local trong `.env`:

```dotenv
POSTGRES_PASSWORD=your-local-database-password
DEMO_SEED_PASSWORD=your-demo-password-at-least-12-characters
```

Sau đó:

```bash
make bootstrap
make migrate
make seed
make up
```

Mở http://127.0.0.1:5173. Tất cả tài khoản local dưới đây dùng password từ
`DEMO_SEED_PASSWORD` trong `.env`:

| Email | Role | Department |
|---|---|---|
| `employee.engineering@example.com` | employee | Engineering |
| `employee.engineering.second@example.com` | employee | Engineering |
| `employee.operations@example.com` | employee | Operations |
| `it.engineering@example.com` | IT | Engineering |
| `it.operations@example.com` | IT | Operations |
| `admin@example.com` | admin | Operations |

Stack mặc định dùng `AI_PROVIDER=fake`; không gọi API trả phí. `make down` dừng container nhưng giữ PostgreSQL, Redis và document volumes. PostgreSQL/Redis không publish ra host; chỉ frontend `5173` và API `8000` bind loopback.

Lệnh gộp sau khi đã cấu hình `.env`:

```bash
make demo
```

Seed account chạy lại không tạo bản sao, chỉ cập nhật hash khi password environment thay đổi
và không tự bật/tắt memory đã được người dùng cấu hình. Seed còn tạo ba thiết bị demo
(Ubuntu/Windows cho Engineering, Windows cho Operations), trạng thái `healthy` mặc định cho
VPN, Docker Registry và GitLab, cùng 18 ticket thuộc nhiều user/phòng ban và cân bằng giữa
`open`, `in_progress`, `resolved`. Published document fixtures vẫn chưa có, nên đây chưa phải
full manual UC-01–UC-12 demo.

## Các route chính

| Route | Chức năng |
|---|---|
| `/chat` | Conversation, message, run/SSE, citation, approval card |
| `/tickets` | Ticket và approval của người dùng |
| `/operations` | Hàng đợi IT, resolve/reopen, service status theo role |
| `/admin/documents` | Upload, preview, process, publish/revoke/version/ACL |
| `/settings/memory` | Consent, device, candidate và fact memory |

Liveness: http://127.0.0.1:8000/api/v1/health/live. Readiness: http://127.0.0.1:8000/api/v1/health/ready.

## Kiểm thử và evaluation

```bash
make test          # isolated PostgreSQL/Redis + backend + frontend checks
make test-e2e      # 7 deterministic browser workflows
make eval          # validate 120 cases + fake development split
make clean-verify  # fresh volumes, migration, seed, 7-service readiness
make docs-check    # relative links trong Markdown
```

`make test`, `make eval` và `make clean-verify` dùng Compose project/volumes tạm rồi tự xóa; không reset database development. Chi tiết command và data boundary ở [infra/commands.md](infra/commands.md).

Live OpenAI chỉ chạy khi có key và opt-in rõ ràng; không chạy trong CI:

```bash
RUN_OPENAI_LIVE_SPIKE=1 make spike-openai-live
RUN_LIVE_EVAL=1 make eval-agent-live
```

Không commit hoặc gửi API key vào chat. Budget guard/token cap vẫn không thay thế việc giám sát billing của nhà cung cấp.

## Backup và restore drill

```bash
make backup
make restore-test
```

Backup nằm trong thư mục Git-ignored `backups/`, gồm PostgreSQL custom dump, document archive, row counts và SHA-256 manifest. Restore test chỉ dùng database `restore_test_*` và Docker volume tạm rồi cleanup; không có target restore đè database đang chạy. Xem [runbook backup](infra/backup-and-restore.md).

## Development trên host

Yêu cầu bổ sung: Python 3.12, uv 0.11.x; Node 22.23.2 nếu không dùng frontend Docker.

```bash
make bootstrap-host
make services-up
make migrate

# Terminal 1
make dev-backend

# Terminal 2
make dev-frontend-docker
```

`make dev-stop` chỉ dừng/xóa frontend development container cố định. Backend host dừng bằng `Ctrl+C`. Nếu cổng 5173 bận:

```bash
docker ps --filter publish=5173
make dev-frontend-docker FRONTEND_DEV_PORT=5174
```

## Báo cáo và giới hạn release

- [G-01–G-09 quality report](reports/evaluation-summary.md)
- [retrieval baseline](reports/retrieval-baseline.md)
- [performance/cost limitations](reports/performance-cost.md)
- [G-10 và release checklist](reports/release-checklist.md)
- [troubleshooting](docs/troubleshooting.md)
- [demo script](docs/demo-script.md)

Hiện tại không tuyên bố production-ready: G-05–G-09 cần live/human/full-stack measurements;
CI remote chưa chạy; business-data seed và manual V1 demo evidence chưa có. Không có bước
deploy server trong CI.

## Cấu trúc repository

```text
backend/app/       FastAPI, auth, LangGraph, RAG, tools/MCP, services, jobs
backend/migrations Alembic migrations
backend/tests/     unit, contract và PostgreSQL/Redis integration
frontend/src/      React routes, API clients và feature UI
frontend/e2e/      deterministic Playwright workflows
data/              self-authored corpus, manifests và seed specification
evals/             120 cases, rubrics và reproducible runner
infra/             Compose, Nginx, images, backup/restore scripts
reports/           reviewed baselines và release evidence
docs/              architecture, ADR, roadmap, demo và troubleshooting
```

Đọc [roadmap](docs/implementation-roadmap.md) để xem checklist và bằng chứng theo work package. Tên portfolio đề xuất: **Stateful IT Support Agent with Evaluated RAG and Approval Workflows**.
