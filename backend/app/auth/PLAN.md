# Đăng nhập và phân quyền

Trạng thái: user/password foundation đã có; session, CSRF và policies đang được triển khai.
Work packages: WP-02, WP-05, WP-08.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 3, 14, 17; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Xây principal tin cậy và policy được dùng chung bởi API, worker, MCP.

## Hợp đồng và trách nhiệm

- Opaque session, token hash trong PostgreSQL, Argon2 password, TTL 8 giờ.
- Visibility company/department/it_only; admin vẫn không đọc conversation/memory riêng của người khác.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `sessions.py`
- `passwords.py`
- `principal.py`
- `policies.py`
- `csrf.py`
- `rate_limit.py`

## Phụ thuộc và phối hợp

- [backend/app/db](../db/PLAN.md)
- [backend/app/repositories](../repositories/PLAN.md)
- [backend/tests/unit](../../tests/unit/PLAN.md)
- [backend/tests/integration](../../tests/integration/PLAN.md)

## Các bước triển khai

- [ ] AUTH-01: Implement login/logout/me, secure cookie và session revocation.
- [ ] AUTH-02: Tạo principal từ user/session DB; đọc lại trạng thái active và quyền khi thực thi.
- [ ] AUTH-03: Tạo policies cho owner resources, IT ticket scope, document ACL và admin actions.
- [ ] AUTH-04: Implement CSRF/Origin validation và Redis rate limiting theo mục 17.
- [ ] AUTH-05: Dùng cùng policy ở read HTTP, source download, MCP calls và approval execution.

## Điều kiện hoàn thành

- [ ] Hai user cùng phòng ban không đọc ticket/conversation/memory của nhau.
- [ ] IT staff chỉ quản lý ticket đúng phòng ban; document ACL áp dụng ở retrieval.
- [ ] Account inactive không thể resume write; credential errors không lộ account tồn tại.
