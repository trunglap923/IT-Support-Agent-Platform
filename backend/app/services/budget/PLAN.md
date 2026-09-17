# Ngân sách và usage ledger

Trạng thái: reservation/ledger input-output cho paid embedding và chat đã triển khai.
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

- [x] COST-01: Định nghĩa operation ID, token caps, reserved/actual/unknown statuses.
- [x] COST-02: Triển khai ledger/reserve atomic và input/output cap cho chat.
- [x] COST-03a: Finalize actual input/output usage và provider_request_id; cached tokens còn WP-13.
- [x] COST-04a: Ghi run counters cho model/retrieval/input/output; retry aggregate còn WP-10.
- [ ] COST-05: Expose safe usage aggregates cho report, không automatic expensive fallback.

## Điều kiện hoàn thành

- [x] Concurrent requests serialize admission và tính cả in-flight reservations; PostgreSQL race test chỉ cho một request qua quota.
- [x] Provider call không chạy khi budget admission bị từ chối.
- [x] Timeout được giữ ở trạng thái unknown với reserved cost, không bị ghi thành cost=0.
