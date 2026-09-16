# Troubleshooting local

## Port 5173 hoặc 8000 đã được dùng

```bash
docker ps --filter publish=5173
docker ps --filter publish=8000
make status
```

Nếu là frontend development container của dự án, chạy `make dev-stop`. Không xóa container không thuộc dự án. Với full stack, chạy `make down` hoặc đổi `FRONTEND_PORT`/`BACKEND_PORT` trong `.env`.

## Frontend báo backend không sẵn sàng

```bash
make status
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
docker compose --file infra/compose.yaml --env-file .env logs api postgres redis
```

Full Compose dùng service names nội bộ. Khi chạy Vite Docker + backend host, dùng `make dev-frontend-docker`; target đã cấu hình host gateway. `ECONNREFUSED ...:8000` thường có nghĩa backend host chưa chạy.

## Login sai dù đã đổi password trong `.env`

Seed lại sau khi đổi `DEMO_SEED_PASSWORD`:

```bash
make seed
```

Lệnh cập nhật Argon2 hash idempotently. Password phải dài tối thiểu 12 ký tự. Email demo là `employee.engineering@example.com`.

## “Yêu cầu bảo mật không hợp lệ”

Dùng đúng URL `http://127.0.0.1:5173`, không đổi sang `localhost` nếu `ALLOWED_WEB_ORIGIN` vẫn là `127.0.0.1`. Reload trang để nhận CSRF cookie mới. Nếu đổi host/cổng, cập nhật `FRONTEND_PORT` và origin cho cùng một host rồi restart stack.

## Readiness 503

Liveness chỉ kiểm tra process; readiness cần PostgreSQL và Redis. Xem health/log bằng:

```bash
make status
docker compose --file infra/compose.yaml --env-file .env logs postgres redis api
```

Không chạy migration bằng cách xóa volume. Dùng `make migrate`.

## Container cũ sau Ctrl+C

```bash
make dev-stop
docker ps -a --filter name=it-support-agent
```

`docker stop` không xóa container thường; dev frontend dùng `--rm` và `make dev-stop` xử lý đúng container cố định. Full stack dùng `make down`, giữ volumes.

## Test service bị lỗi hoặc dữ liệu test còn lại

`make test` dùng project `it-support-agent-tests` và trap cleanup. Nếu host/Docker bị tắt đột ngột:

```bash
docker compose --project-name it-support-agent-tests \
  --file infra/compose.yaml --file infra/compose.test.yaml --env-file .env \
  down --volumes --remove-orphans
```

Command này chỉ xóa project test có tên chính xác, không xóa volumes development.

## Backup/restore test lỗi

Chạy `make backup` trước. Bundle phải nằm dưới `backups/` và đủ `manifest.json`. Restore test từ chối path ngoài thư mục này và không restore vào DB development. Chi tiết: [backup runbook](../infra/backup-and-restore.md).

## OpenAI hoặc Langfuse

Fake mode không cần key. `AI_PROVIDER=openai` yêu cầu `OPENAI_API_KEY`; live spike/eval còn yêu cầu biến opt-in riêng. Không đưa key vào log, issue, ảnh chụp hoặc commit. Langfuse thiếu key sẽ dùng no-op trong fake mode.

## Xem log mà không lộ secret

Ưu tiên log theo service và không in `.env`:

```bash
docker compose --file infra/compose.yaml --env-file .env logs --tail=200 api worker-agent
```

Khi báo lỗi, gửi status, stack trace đã lọc và commit hash; không gửi cookie, CSRF token, API key hoặc database URL có password.
