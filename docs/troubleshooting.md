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

Fake mode không cần key. `TEXT_PROVIDER=openai` hoặc `EMBEDDING_PROVIDER=openai` yêu cầu
`OPENAI_API_KEY`; live spike/eval và paid re-index còn yêu cầu biến opt-in riêng. Không đưa
key vào log, issue, ảnh chụp hoặc commit. Langfuse thiếu key sẽ dùng no-op trong fake mode.

Kiểm tra Langfuse từ cùng container chạy Agent:

```bash
docker compose --file infra/compose.yaml --env-file .env exec worker-agent \
  python -c 'from langfuse import get_client; print(get_client().auth_check())'
```

Nếu kết quả là `False`, kiểm tra `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` và
`LANGFUSE_BASE_URL` có đúng project/data region. Nếu xác thực thành công nhưng chưa thấy trace,
bật tạm `LANGFUSE_DEBUG=true`, chạy lại `make up`, gửi đúng một yêu cầu rồi xem
`make logs-agent`. Tắt debug sau khi điều tra. Không tắt các biến `OPENINFERENCE_HIDE_*`; chúng
giữ token, latency và cấu trúc Agent/tool span trong khi loại nội dung chat và tài liệu khỏi trace.

Nếu Docker build báo `UnknownIssuer`, đặt `HOST_CA_BUNDLE` tới CA bundle của host (mặc định
Linux là `/etc/ssl/certs/ca-certificates.crt`). Compose chỉ mount file này như BuildKit
secret trong bước cài dependency; certificate không được copy vào image.

## Xem log mà không lộ secret

Theo dõi toàn bộ luồng chat ở API và agent worker:

```bash
make logs-agent
```

Mỗi dòng chẩn đoán là JSON và có `run_id`. Có thể lọc một lần chạy cụ thể:

```bash
make logs-agent | rg --line-buffered 'RUN_ID_CAN_XEM'
```

Các mốc chính gồm `chat.submission.accepted`, `worker.run.claimed`,
`agent.action.decided`, `retrieval.search.completed`, `agent.evidence.selected`,
`agent.generation.*`, `worker.stream.delta.persisted`, `worker.result.committed`,
`sse.event.delivered` và `worker.run.failed`.

Mặc định `LOG_PROMPTS=false`: log có độ dài, hash, điểm retrieval, nguồn, token usage và
traceback nhưng không có nội dung chat/tài liệu/câu trả lời. Chỉ bật tạm thời trên môi trường
development khi cần xem nội dung từng delta:

```ini
LOG_PROMPTS=true
```

Sau khi đổi, chạy `make up`; điều tra xong nên trả lại `false`. Ưu tiên log theo service và
không in `.env`:

```bash
docker compose --file infra/compose.yaml --env-file .env logs --tail=200 api worker-agent
```

Khi báo lỗi, gửi status, stack trace đã lọc và commit hash; không gửi cookie, CSRF token, API key hoặc database URL có password.
