# Infrastructure — môi trường local và vận hành

Trạng thái: PostgreSQL/pgvector và Redis development services đã có; application services chưa triển khai.
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
- [ ] INFRA-01c: Khóa images/healthchecks cho application services còn lại.
- [ ] INFRA-02: Thiết lập role env cho API/worker/migration, DB users tối thiểu và document storage quyền hợp lý.
- [ ] INFRA-03: Proxy SPA + /api cùng origin; tắt buffering và đặt timeout thích hợp cho SSE.
- [ ] INFRA-04: Nối Celery queues: agent concurrency=2, background=1 xử lý maintenance, chỉ một scheduler.
- [ ] INFRA-05: Thêm backup DB + document files/manifest và restore drill vào DB/volume test riêng; ghi recovery limitations.
- [ ] INFRA-06: Viết root Makefile theo mục 20.4 sau khi các command thực sự tồn tại, không đặt placeholder báo thành công.

## Điều kiện hoàn thành

- [ ] Máy sạch chạy setup/migrate/seed/demo theo README mà không cần dữ liệu private.
- [ ] Restart worker/Redis không mất ticket receipt hoặc làm trùng write.
- [ ] Restore vào target test được đối chiếu dữ liệu/chunks/citations; không chạm DB đang dùng.
