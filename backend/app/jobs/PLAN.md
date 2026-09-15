# Workers, scheduler và recovery

Trạng thái: Celery queues/scheduler và fake task foundation đã có; DB claim/reconcile được bổ sung trong WP-03.
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
- [ ] JOB-02: Commit queued record trước enqueue; xây periodic reconcile mỗi 30 giây.
- [ ] JOB-03: Claim worker ownership, heartbeat và stale recovery; không chạy đồng thời cùng run.
- [ ] JOB-04: Nối checkpoint/receipt recovery và expire approval; job failures có safe error code.
- [ ] JOB-05: Chạy cleanup theo retention/epoch, đóng clients/subprocess đúng vòng đời.

## Điều kiện hoàn thành

- [ ] Mất Redis giữa commit/enqueue được reconcile sau phục hồi.
- [ ] Duplicate delivery/crash không tạo thêm ticket hoặc active memory đã xóa.
- [ ] OpenAI calls/retries còn chịu budget toàn run; job attempt tối đa 3.
