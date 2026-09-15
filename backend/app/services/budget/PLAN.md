# Ngân sách và usage ledger

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-04, WP-06, WP-12, WP-13.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 9.4, 16.3; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Chặn vượt quota ứng dụng và lưu chi phí thực của mọi AI operation.

## Hợp đồng và trách nhiệm

- Một ledger dùng chung chat/embedding/memory/eval qua provider wrapper.
- Default 1 USD/ngày, 10 USD/tháng; cấu hình và price_version theo plan.md.
- Timeout unknown usage giữ reservation bảo thủ, không tự hoàn quota như call miễn phí.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `service.py`
- `pricing.py`
- `reservations.py`

## Phụ thuộc và phối hợp

- [backend/app/db](../../db/PLAN.md)
- [backend/app/repositories](../../repositories/PLAN.md)
- [backend/app/providers](../../providers/PLAN.md)
- [backend/app/observability](../../observability/PLAN.md)

## Các bước triển khai

- [ ] COST-01: Định nghĩa operation/attempt ID, token caps, reserved/actual/unknown statuses.
- [ ] COST-02: Triển khai ledger/reserve atomic tối thiểu trước paid embedding đầu tiên ở WP-04; mở rộng input/output cap cho chat ở WP-06.
- [ ] COST-03: Finalize actual usage gồm cached tokens, ghi provider_request_id.
- [ ] COST-04: Áp dụng run counters qua retries/repair và worker replay.
- [ ] COST-05: Expose safe usage aggregates cho report, không automatic expensive fallback.

## Điều kiện hoàn thành

- [ ] Concurrent requests tính cả in-flight reservations nên không vượt admission quota.
- [ ] Không thực hiện provider call khi budget thiếu.
- [ ] Timeout và job retry không ghi cost=0 hoặc làm mất attempt đã tính.
