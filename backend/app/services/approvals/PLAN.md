# Draft và xác nhận hành động

Trạng thái: approval lifecycle, checkpoint resume và receipt recovery WP-08–WP-10 đã triển khai.
Work packages: WP-08, WP-10.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 11, 14, 15; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Lưu preview được duyệt và bảo vệ action khỏi thay arguments/replay.

## Hợp đồng và trách nhiệm

- Draft có action_id, owner/run, canonical_args, hash, version và expiry 15 phút.
- pending → approved → executed; pending → rejected; chưa execute có thể expired.
- Approve không cấp thêm quyền; receipt đã tồn tại trả lại khi replay đúng owner/hash.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `service.py`
- `canonicalization.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [backend/app/auth](../../auth/PLAN.md)
- [backend/app/services/conversations](../conversations/PLAN.md)
- [backend/app/services/tickets](../tickets/PLAN.md)
- [backend/app/jobs](../../jobs/PLAN.md)
- [backend/tests/integration](../../../tests/integration/PLAN.md)

## Các bước triển khai

- [x] APR-01: Validate draft từ model hoặc manual form bằng cùng schema.
- [x] APR-02: Upsert draft idempotent theo action_id, chỉ phát preview khi graph pause đã lưu.
- [x] APR-03: Approve/reject bằng row lock/version, xác minh owner/account/expiry.
- [x] APR-04: Khóa arguments đã duyệt, enqueue resume bằng DB decision.
- [x] APR-05: Sửa draft bằng hủy rồi tạo mới (expire pending run và phát event đã hoàn thành).

## Điều kiện hoàn thành

- [x] Sai owner/version/hash/expiry/inactive user không tạo ticket.
- [x] Hai approve đồng thời không tạo hai action; replay đúng trả trạng thái cũ.
- [x] Checkpoint/browser refresh không làm mất preview, browser không tự gửi LangGraph Command.
