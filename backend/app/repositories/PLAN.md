# Queries và data access

Trạng thái: scoped query/repository layer và cursor pagination đã có; query-plan evidence còn thiếu.
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

- [x] REPO-01: Owner conversation/run/memory và employee/IT/admin ticket scope được áp ngay trong SQL.
- [x] REPO-02: Retrieval, history redaction và source download dùng chung current/effective/ACL predicate.
- [x] REPO-03: Run/approval/ticket/document/usage writes dùng row locks, expected version và unique conflict handling.
- [x] REPO-04: Thêm cursor pagination ổn định bằng timestamp + ID.
- [ ] REPO-05: Event/job/receipt lookups đã có; query-plan evidence cho dataset lớn còn thiếu.

## Điều kiện hoàn thành

- [x] PostgreSQL integration tests chứng minh own/department/document boundaries.
- [x] Protected resources được scope trong query; UI không nhận object trái quyền để tự lọc.
- [x] Ticket/approval/run/document writes và events/receipts rollback cùng transaction khi lỗi.
