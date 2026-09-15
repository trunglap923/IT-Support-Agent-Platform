# Database migrations

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-02, WP-04, WP-07, WP-08, WP-12, WP-14.
Nguồn: [kế hoạch tổng](../../plan.md), mục 13, 20; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Quản lý thay đổi schema theo từng milestone và chạy trên DB sạch.

## Hợp đồng và trách nhiệm

- Alembic quản lý application schema; checkpointer setup có bước rõ và được version-lock.
- Migrations chạy one-off trước app, seed tách riêng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `env.py`
- `script.py.mako`
- `versions/`

## Phụ thuộc và phối hợp

- [backend/app/db](../app/db/PLAN.md)
- [infra](../../infra/PLAN.md)
- [backend/tests/integration](../tests/integration/PLAN.md)
- [data/seed](../../data/seed/PLAN.md)

## Các bước triển khai

- [ ] MIG-01: Cấu hình Alembic qua migration credential; tạo extension vector có kiểm tra quyền.
- [ ] MIG-02: Chia revision theo feature: identity/run → docs/usage ledger WP-04 → ticket/service_states WP-07 → approval/write constraints WP-08 → memory WP-12.
- [ ] MIG-03: Thêm unique, FK, partial indexes và current-version integrity trong migrations.
- [ ] MIG-04: Viết upgrade checks từ DB trống và từ revision trước.
- [ ] MIG-05: Ghi rollback/backup policy; restore drill dùng DB riêng.

## Điều kiện hoàn thành

- [ ] Upgrade tới head tái lập được trên DB test.
- [ ] Constraints race-critical tồn tại sau upgrade.
- [ ] Không đổi schema ngoài migrations hoặc chạy destructive reset trên runtime DB.
