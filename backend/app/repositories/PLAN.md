# Queries và data access

Trạng thái: user identity repository đã có; scoped resource repositories đang được bổ sung.
Work packages: WP-02, WP-05, WP-07, WP-11, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 5.3, 13; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp queries có scope và hỗ trợ transaction của business services.

## Hợp đồng và trách nhiệm

- Nhận DB session/transaction và scope tường minh; không nhận raw SQL từ user/model.
- Services sở hữu transaction boundary; repositories không âm thầm commit.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `users.py`
- `conversations.py`
- `tickets.py`
- `documents.py`
- `runs.py`
- `memory.py`
- `usage.py`

## Phụ thuộc và phối hợp

- [backend/app/db](../db/PLAN.md)
- [backend/app/auth](../auth/PLAN.md)
- [backend/tests/integration](../../tests/integration/PLAN.md)

## Các bước triển khai

- [ ] REPO-01: Tạo scoped lookup/list cho owner resources và IT/admin ticket scope.
- [ ] REPO-02: Xây queries document ACL/current/effective version cho retrieval/download.
- [ ] REPO-03: Cung cấp row locks/conditional updates/unique conflict mapping.
- [ ] REPO-04: Thêm cursor pagination ổn định bằng timestamp + ID.
- [ ] REPO-05: Thêm event/job lookup và receipt-by-approval; kiểm tra query plans khi cần.

## Điều kiện hoàn thành

- [ ] Test trên PostgreSQL thật chứng minh own/department boundaries.
- [ ] Không fetch object trái quyền rồi lọc riêng ở UI.
- [ ] Một service transaction rollback toàn bộ write/audit khi có lỗi.
