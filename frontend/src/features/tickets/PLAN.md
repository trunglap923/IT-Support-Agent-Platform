# UI — ticket cá nhân và xử lý của IT

Trạng thái: ticket list, manual draft/approval và IT transition UI WP-09 đã triển khai.
Work packages: WP-09.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 3, 4, 7, 11, 14; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Xem/tạo ticket và cho IT cập nhật ticket trong phạm vi được cấp.

## Hợp đồng và trách nhiệm

- Employee xem ticket của mình; IT xem thêm ticket phòng ban; admin có scope quản trị theo backend.
- Form tạo thủ công đi qua ticket-drafts, run kind manual_ticket và approval, không direct insert.
- Trạng thái incident memory chỉ theo trạng thái ticket thật, không theo nút UI hoặc lời model.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `TicketsPage.tsx`
- `TicketDetail.tsx`
- `TicketDraftForm.tsx`
- `TicketStatusForm.tsx`
- `queries.ts`

## Phụ thuộc và phối hợp

- [backend/app/services/tickets](../../../../backend/app/services/tickets/PLAN.md)
- [backend/app/services/approvals](../../../../backend/app/services/approvals/PLAN.md)
- [frontend/src/features/chat](../chat/PLAN.md)

## Các bước triển khai

- [x] UITKT-01a: Làm danh sách ticket cá nhân và IT queue theo API.
- [ ] UITKT-01b: Thêm detail route và bộ lọc owner/status/issue_type.
- [x] UITKT-02: Form nhập title/description/issue_type/severity rồi chuyển tới preview để xác nhận.
- [x] UITKT-03: Tạo chế độ IT và form status update kèm xử lý version conflict.
- [ ] UITKT-04: Invalidate danh sách/detail sau receipt hoặc cập nhật; liên kết từ chat tới ticket đã tạo.

## Điều kiện hoàn thành

- [x] Employee không đọc ticket người khác qua owner-scoped API.
- [x] IT sai phòng ban bị chặn, account inactive không ghi được.
- [x] Form thủ công và chat cùng bảo đảm approval/idempotency ở backend.
