# Infrastructure — môi trường local và vận hành

Trạng thái: stack local 7 service với application images, health dependencies và volumes đã có.
Work packages: WP-01, WP-02, WP-03, WP-10, WP-14.
Nguồn: [kế hoạch tổng](../plan.md), mục 15, 17, 20; [thứ tự triển khai](../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp Docker Compose tái lập được, cấu hình an toàn và cách backup/restore kiểm chứng.

## Hợp đồng và trách nhiệm

- Bảy service: frontend, api, worker-agent, worker-background, scheduler, postgres, redis.
- Backend cùng image; MCP là stdio subprocess trong worker-agent; không dựng public MCP hoặc self-host Langfuse V1.
- Postgres/Redis/storage có volume; Redis AOF/noeviction, chỉ mở cổng cần thiết ở localhost.
- Migration và seed là bước explicit, không tự reset dữ liệu mỗi lần start.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `compose.yaml`
- `Dockerfile.backend`
- `Dockerfile.frontend`
- `nginx.conf`
- `scripts/backup.sh`
- `scripts/restore-test.sh`

## Phụ thuộc và phối hợp

- [backend](../backend/PLAN.md)
- [backend/app/jobs](../backend/app/jobs/PLAN.md)
- [backend/migrations](../backend/migrations/PLAN.md)
- [frontend](../frontend/PLAN.md)
- [docs](../docs/PLAN.md)

## Các bước triển khai

- [x] INFRA-01a: Khóa PostgreSQL 17/pgvector image và tạo healthcheck không gọi model.
- [x] INFRA-01b: Khóa Redis image, AOF/noeviction và healthcheck không mở public.
- [x] INFRA-01c: Khóa images/healthchecks cho application services còn lại.
- [x] INFRA-02: Tách API/worker runtime env; migration credential chỉ được truyền vào one-shot command.
- [x] INFRA-03: Proxy SPA + /api cùng origin; tắt buffering và đặt timeout thích hợp cho SSE.
- [x] INFRA-04: Nối Celery queues agent/background và một scheduler có health dependency.
- [x] INFRA-05: Backup DB + document archive có checksum manifest; restore drill chỉ dùng DB/volume tạm và ghi recovery limitations.
- [x] INFRA-06: Root Makefile có các command tái lập; test/eval/clean verification dùng Compose project và volume cô lập.

## Điều kiện hoàn thành

- [x] Máy sạch chạy build/migrate/seed và đủ 7 service bằng `make clean-verify`, dùng fake AI và dữ liệu tạm.
- [ ] Restart worker/Redis không mất ticket receipt hoặc làm trùng write.
- [x] Restore vào target test đối chiếu Alembic revision, row counts gồm chunks/messages và checksum mọi document; không chạm DB đang dùng.
