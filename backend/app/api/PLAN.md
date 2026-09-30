# HTTP API và SSE

Trạng thái: auth/run/chat, approval/ticket/service, document và memory routes đã triển khai.
Work packages: WP-02, WP-03, WP-08, WP-11, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 14; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp HTTP contract cho web và chuyển request đã xác thực tới services.

## Hợp đồng và trách nhiệm

- Prefix /api/v1; request/response models và error envelope theo mục 14.
- HTTP input không nhận actor/role để thay principal; SSE chỉ đọc events đúng owner.
- Đầu ra là DTO an toàn, không trả ORM object, checkpoint hoặc raw provider result.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `auth.py`
- `conversations.py`
- `runs.py`
- `approvals.py`
- `tickets.py`
- `documents.py`
- `memory.py`
- `services.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [backend/app/auth](../auth/PLAN.md)
- [backend/app/services](../services/PLAN.md)
- [backend/app/repositories](../repositories/PLAN.md)
- [frontend/src/api](../../../frontend/src/api/PLAN.md)

## Các bước triển khai

- [x] API-01a: Khai báo schemas/OpenAPI cho login, logout và current session.
- [x] API-01b: Khai báo response schema/OpenAPI cho run snapshot và event stream ở WP-03.
- [x] API-02a: Implement auth routes mỏng; kiểm tra Origin/CSRF với logout.
- [x] API-02b: Implement chat/approval/ticket/service routes cùng CSRF/policy tương ứng.
- [x] API-03: Tạo GET run snapshot/events hỗ trợ Last-Event-ID/after_sequence, heartbeat và ownership.
- [x] API-04a: Bổ sung routes approval, ticket IT/service status và manual ticket draft.
- [x] API-04b1: Bổ sung admin PDF upload và draft preview routes.
- [x] API-04b2a: Bổ sung document version/process/publish/revoke/ACL routes.
- [x] API-04b2b: Bổ sung owner-scoped device/candidate/fact memory routes.
- [x] API-05a: Chuẩn hóa error envelope cho 401/403/404/409/410/413/422/429/503, request ID và Retry-After.
- [ ] API-05b: Thêm cursor pagination cho các list API lớn.

## Điều kiện hoàn thành

- [x] Integration tests chứng minh đúng owner, CSRF và version conflict cho routes hiện có.
- [ ] Cursor pagination cho các list lớn ở WP hoàn thiện API.
- [x] Reconnect SSE chỉ đọc event đã persist và không tạo run/message/job mới.
- [ ] Endpoint chưa triển khai không được mô tả là đang hoạt động trong README.
