# Unit tests

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-02, WP-04, WP-06, WP-08, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 19.1; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Kiểm tra policy, transformations và state transitions nhanh, có kết quả cố định.

## Hợp đồng và trách nhiệm

- Sử dụng fixtures thuần dữ liệu, fake clock/provider.
- Không cần PostgreSQL, Redis hoặc mạng cho suite này.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `test_policies.py`
- `test_chunking.py`
- `test_context.py`
- `test_approval_hash.py`
- `test_memory_rules.py`
- `test_budget.py`

## Phụ thuộc và phối hợp

- [backend/app/auth](../../app/auth/PLAN.md)
- [backend/app/rag/chunking](../../app/rag/chunking/PLAN.md)
- [backend/app/agent/context](../../app/agent/context/PLAN.md)
- [backend/app/services/approvals](../../app/services/approvals/PLAN.md)

## Các bước triển khai

- [ ] UNIT-01: Test role/owner/document scope với deny-by-default.
- [ ] UNIT-02: Test canonical args/hash, expected versions và approval expiry boundaries.
- [ ] UNIT-03: Test chunk limits/code preservation, context token budget và tool result pairs.
- [ ] UNIT-04: Test memory epoch/allowlist/device conflict và cost reservation arithmetic.

## Điều kiện hoàn thành

- [ ] Các decision branch có negative cases quan trọng.
- [ ] Tests không khẳng định model quality hoặc database isolation mà không chạy chúng.
