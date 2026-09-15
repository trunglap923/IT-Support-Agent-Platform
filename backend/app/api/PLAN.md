# HTTP API và SSE

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
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

- [ ] API-01: Khai báo schemas và OpenAPI cho auth/conversation/run trước khi UI tích hợp.
- [ ] API-02: Implement routes mỏng cho services; kiểm tra CSRF với state-changing requests.
- [ ] API-03: Tạo GET events hỗ trợ Last-Event-ID/after_sequence, heartbeat và snapshot fallback.
- [ ] API-04: Bổ sung routes approval, ticket IT, document admin, memory và manual ticket draft theo từng WP.
- [ ] API-05: Chuẩn hóa 401/403/404/409/410/413/422/429/503, cursor pagination và Retry-After.

## Điều kiện hoàn thành

- [ ] Integration tests chứng minh đúng owner, CSRF, conflict và pagination.
- [ ] Reconnect SSE không tạo run/job mới; event chỉ phát sau persist.
- [ ] Endpoint chưa triển khai không được mô tả là đang hoạt động trong README.
