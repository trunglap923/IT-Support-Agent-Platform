# Seed — người dùng, thiết bị, ticket và dịch vụ

Trạng thái: đặc tả/schema M0 đã có; fixture và seed command chưa triển khai.
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
- [ ] SEED-01b: Map stable keys sang DB ids qua seed command ở backend.
- [ ] SEED-02: Tạo thiết bị laptop Ubuntu/desktop Windows cùng một user để kiểm thử memory isolation.
- [ ] SEED-03: Chuẩn bị ticket open/in_progress/resolved và kịch bản reopen về trạng thái theo mục 11, không thêm enum reopened.
- [ ] SEED-04: Tạo kịch bản hoạt động bình thường, VPN outage và lỗi phụ thuộc theo mode được backend cho phép.
- [ ] SEED-05: Viết seed idempotent và dry-run/summary; reset chỉ trên môi trường test có guard.

## Điều kiện hoàn thành

- [ ] Chạy seed hai lần không nhân đôi user/ticket/document.
- [ ] User cùng phòng ban và khác phòng ban đều có negative cases riêng.
- [ ] Không tự bật consent hoặc tạo active memory của người dùng ngoài fixture test explicit.
