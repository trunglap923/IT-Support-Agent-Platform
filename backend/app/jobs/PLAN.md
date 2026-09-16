# Workers, scheduler và recovery

Trạng thái: Celery queues/scheduler, DB claim, lease/heartbeat và reconcile/recovery WP-10 đã triển khai.
Work packages: WP-03, WP-04, WP-08, WP-10, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 15, 20.2; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Chạy agent/ingestion/memory ngoài HTTP request với trạng thái durable trong DB.

## Hợp đồng và trách nhiệm

- Queue payload chỉ có ID; DB là nguồn status, Redis là broker.
- agent worker concurrency=2; background=1, xử lý cả maintenance; một beat instance.
- Claim idempotent, leases/advisory lock và bounded attempts theo plan.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `celery_app.py`
- `agent_tasks.py`
- `ingestion_tasks.py`
- `memory_tasks.py`
- `maintenance.py`
- `leases.py`

## Phụ thuộc và phối hợp

- [backend/app/services/conversations](../services/conversations/PLAN.md)
- [backend/app/agent](../agent/PLAN.md)
- [backend/app/rag/ingestion](../rag/ingestion/PLAN.md)
- [backend/app/memory](../memory/PLAN.md)
- [infra](../../../infra/PLAN.md)

## Các bước triển khai

- [x] JOB-01: Route agent/background queues, JSON serialization, prefetch=1 và bounded time limits.
- [x] JOB-02: Commit queued record trước enqueue; periodic reconcile chạy mỗi 30 giây.
- [x] JOB-03a: Claim worker bằng row lock + idempotency event; delivery trùng không chạy lại run.
- [x] JOB-03b: Thêm heartbeat/lease và stale recovery đầy đủ ở WP-10.
- [x] JOB-04a: Nối checkpoint/receipt recovery; timeout và exhausted attempts có safe error code.
- [ ] JOB-04b: Thêm maintenance job chủ động expire approval đang pending.
- [ ] JOB-05: Chạy cleanup theo retention/epoch, đóng clients/subprocess đúng vòng đời.

## Điều kiện hoàn thành

- [x] Mất Redis giữa commit/enqueue giữ run queued và được reconcile sau phục hồi.
- [x] Duplicate delivery/crash không tạo thêm ticket.
- [x] Extraction hoàn tất sau edit/delete bị discard khi captured epoch đã cũ.
- [x] Job attempt tối đa 3 và stale lease hết hạn có thể được worker khác reclaim.
- [ ] OpenAI calls/retries còn chịu budget toàn run trong worker production.
