# Conversation, run và event store

Trạng thái: persistence, history/final response, event/SSE và lease recovery WP-02–WP-10 đã có.
Work packages: WP-02, WP-03, WP-06, WP-10.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 9.1, 13, 14.3, 15; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Quản lý lịch sử, trạng thái run và các sự kiện browser đọc lại được.

## Hợp đồng và trách nhiệm

- Unique(actor_id, client_request_id); khác payload cùng key trả conflict.
- Một active run/conversation, gồm waiting_approval; kind chat/manual_ticket.
- Messages/run events được persist trước khi UI nhận thông báo.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `service.py`
- `runs.py`
- `events.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [backend/app/repositories](../../repositories/PLAN.md)
- [backend/app/auth](../../auth/PLAN.md)
- [backend/app/jobs](../../jobs/PLAN.md)
- [backend/app/services/approvals](../approvals/PLAN.md)
- [backend/app/rag/citations](../../rag/citations/PLAN.md)

## Các bước triển khai

- [x] CONV-01: Implement create/list conversation và owner-filtered message history.
- [x] CONV-02: Tạo message+queued run cùng transaction, trả run cũ cho request replay hợp lệ.
- [x] CONV-03a: Tạo validated status/version transitions, terminal states và idempotent event sequence.
- [x] CONV-03b: Thêm worker lease/heartbeat và stale recovery đầy đủ ở WP-10.
- [x] CONV-04a: Implement finalized message/outcome và citation source payload.
- [x] CONV-04b: Owner-scoped feedback gắn message và run, idempotent update, có CSRF/API tests.
- [x] CONV-05: User cancel chỉ queued/waiting_approval, có CSRF/version/idempotency; maintenance chốt approval expiry.

## Điều kiện hoàn thành

- [x] Gửi cùng request hai lần chỉ có một run; race insert được unique constraint chặn.
- [x] SSE replay đọc events theo owner/cursor và không gọi agent.
- [x] Worker lỗi vẫn truy được persisted run status/event.
- [x] Recheck ACL khi render citation lịch sử sau document revoke ở WP-11.
