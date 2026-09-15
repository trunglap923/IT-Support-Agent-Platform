# Conversation, run và event store

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
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

- [ ] CONV-01: Implement create/list conversation và owner-filtered message history.
- [ ] CONV-02: Tạo message+queued run cùng transaction, trả run cũ cho request replay hợp lệ.
- [ ] CONV-03: Tạo claim/status/version/lease transitions và event sequence.
- [ ] CONV-04: Implement finalized message/outcome và liên kết source/feedback.
- [ ] CONV-05: Cancel chỉ queued/waiting_approval; chốt expiry để không giữ conversation kẹt mãi.

## Điều kiện hoàn thành

- [ ] Gửi cùng request hai lần chỉ có một run; race insert được unique constraint chặn.
- [ ] SSE replay đọc events không gọi agent.
- [ ] Lịch sử trái ACL bị ẩn qua citation policy; worker lỗi vẫn truy được status.
