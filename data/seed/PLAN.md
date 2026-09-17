# Seed — người dùng, thiết bị, ticket và dịch vụ

Trạng thái: department, account, device, service-state, ticket và published-knowledge seed đã có.
Work packages: WP-01, WP-02, WP-04, WP-07, WP-12.
Nguồn: [kế hoạch tổng](../../plan.md), mục 3, 6, 13, 20.4; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp fixtures nhỏ nhưng bao phủ ownership, phòng ban, trạng thái ticket và memory nhiều thiết bị.

## Hợp đồng và trách nhiệm

- Sáu user: hai employee Engineering, một employee Operations, một IT mỗi phòng ban và một admin.
- Khoảng 20 ticket; dịch vụ theo ids/enum từ kế hoạch tổng; status response gắn source=simulated_monitor.
- Password lấy từ DEMO_SEED_PASSWORD và hash khi seed, không commit plaintext; mặc định memory off.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `company.json`
- `departments.json`
- `users.json`
- `devices.json`
- `tickets.json`
- `service_states.json`
- `scenarios.json`

## Phụ thuộc và phối hợp

- [backend/app/db](../../backend/app/db/PLAN.md)
- [backend/app/auth](../../backend/app/auth/PLAN.md)
- [backend/app/services/tickets](../../backend/app/services/tickets/PLAN.md)
- [backend/app/services/service_status](../../backend/app/services/service_status/PLAN.md)
- [data/manifests](../manifests/PLAN.md)

## Các bước triển khai

- [x] SEED-01a: Viết manifest seed schema và quy ước stable keys.
- [x] SEED-01b: Upsert hai department và sáu account theo natural key; hash password runtime và không nhân bản khi chạy lại.
- [x] SEED-02: Tạo Ubuntu/Windows cho cùng employee Engineering và Windows cho employee Operations.
- [x] SEED-03: Tạo 18 ticket cân bằng open/in_progress/resolved; reopen vẫn là transition, không thêm enum reopened.
- [ ] SEED-04: Tạo kịch bản hoạt động bình thường, VPN outage và lỗi phụ thuộc theo mode được backend cho phép.
- [x] SEED-05: Viết full seed idempotent với dry-run/summary; không cung cấp reset cho database đang dùng.

## Điều kiện hoàn thành

- [x] Chạy seed hai lần không nhân đôi user/ticket/document/chunk.
- [x] Dry-run validate và phân loại created/updated/unchanged nhưng rollback mọi thay đổi.
- [x] User cùng phòng ban và khác phòng ban đều có negative cases riêng.
- [x] Không tự bật consent hoặc tạo active memory của người dùng ngoài fixture test explicit.
