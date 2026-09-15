# Trạng thái dịch vụ giả lập

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-07, WP-10.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 3, 6.1, 10, 15.4; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp nguồn live-state mô phỏng để demo tool use và lỗi dependency.

## Hợp đồng và trách nhiệm

- Chỉ service_id vpn/registry/gitlab; status healthy/degraded/down/unknown.
- Result có checked_at và source=simulated_monitor.
- Admin đổi preset chỉ trong DEMO_MODE; model không có tool đổi trạng thái.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `service.py`
- `presets.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [data/seed](../../../../data/seed/PLAN.md)
- [backend/app/mcp_server](../../mcp_server/PLAN.md)
- [backend/app/auth](../../auth/PLAN.md)
- [frontend/src/features/services](../../../../frontend/src/features/services/PLAN.md)

## Các bước triển khai

- [ ] STATUS-01: Seed ba service records ổn định trong service_states.
- [ ] STATUS-02: Read current status kèm timestamp và safe envelope.
- [ ] STATUS-03: Thêm demo fault modes none/timeout/error; fault không sửa policy/identity.
- [ ] STATUS-04: Validate admin update và ghi audit.

## Điều kiện hoàn thành

- [ ] UC-02 dùng MCP status tool, không trả từ RAG.
- [ ] Unknown/timeout không được render thành healthy.
- [ ] Registry healthy không bị diễn giải thành máy user kết nối chắc chắn thành công.
