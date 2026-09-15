# Ticket và hàng đợi IT

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-07, WP-08, WP-09, WP-10.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 3, 10, 11.2, 11.3; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Tạo ticket một lần sau approval và quản lý trạng thái theo scope IT.

## Hợp đồng và trách nhiệm

- Agent read chỉ own open tickets; IT UI dùng scope department/admin.
- Unique approval_id; ticket + approval executed + audit commit cùng transaction.
- open → in_progress → resolved; resolved có thể reopen; resolution_note bắt buộc khi resolved.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `service.py`
- `transitions.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [backend/app/services/approvals](../approvals/PLAN.md)
- [backend/app/repositories](../../repositories/PLAN.md)
- [backend/app/memory](../../memory/PLAN.md)
- [frontend/src/features/tickets](../../../../frontend/src/features/tickets/PLAN.md)

## Các bước triển khai

- [ ] TKT-01: Implement own-ticket read và IT scoped list/detail.
- [ ] TKT-02: Validate title/description/severity/issue_type/device owner.
- [ ] TKT-03: Create-from-approved-action recheck owner/hash/expiry và execution ownership.
- [ ] TKT-04: Return existing receipt trước retry write; không báo thành công khi outcome unknown.
- [ ] TKT-05: Implement IT status updates bằng expected version và ticket_events; nối incident records đang tồn tại.

## Điều kiện hoàn thành

- [ ] Double-click/concurrent job/crash-after-commit đều cho đúng một ticket.
- [ ] User không đóng/xóa ticket qua agent; IT scope không vượt phòng ban.
- [ ] Ticket created không tự được coi là incident resolved.
