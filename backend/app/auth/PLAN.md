# Đăng nhập và phân quyền

Trạng thái: user/password, session, CSRF và role policies WP-02 đã triển khai và đạt PostgreSQL integration gate local.
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

- [x] AUTH-01a: Implement login/logout/me, opaque cookie, expiry và session revocation.
- [x] AUTH-01b: Hoàn thiện secure cookie/CSRF enforcement theo môi trường.
- [x] AUTH-02: Tạo principal từ user/session DB; đọc lại trạng thái active và quyền khi thực thi.
- [x] AUTH-03a: Tạo dependency role policy và deny role không phù hợp.
- [x] AUTH-03b: Tạo policies owner, IT ticket scope và document ACL ở WP tương ứng.
- [x] AUTH-04a: Implement CSRF synchronizer token và Origin validation.
- [x] AUTH-04b: Implement Redis login rate limiting, hashed bucket, Retry-After và fail-closed khi Redis lỗi.
- [x] AUTH-05: HTTP/source download recheck principal + SQL scope; MCP inject trusted actor; approval execution recheck owner/account/device/hash.

## Điều kiện hoàn thành

- [x] Repository và DB constraint ngăn hai user đọc/tạo run trên conversation của nhau; ticket/memory kiểm tra ở WP tương ứng.
- [x] IT staff chỉ quản lý ticket đúng phòng ban; document ACL áp dụng ở retrieval.
- [x] Account inactive bị từ chối ngay cả khi session cũ còn hạn.
- [x] Kiểm chứng credential errors không lộ account tồn tại; implementation dùng generic error và dummy hash.
