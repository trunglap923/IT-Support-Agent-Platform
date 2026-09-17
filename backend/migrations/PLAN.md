# Database migrations

Trạng thái: Alembic và 17 feature revisions qua ticket device ownership đã có; fresh upgrade/restore test local đạt.
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

- [x] MIG-01: Cấu hình Alembic qua migration credential; tạo extension vector có kiểm tra quyền.
- [x] MIG-02a: Tạo revision identity riêng cho department/user.
- [x] MIG-02b: Tạo revisions session và conversation/run/event theo feature WP-02.
- [x] MIG-02c: Chia revisions docs/ticket/approval/memory theo feature.
- [x] MIG-03a: Thêm unique, ownership FK và partial active-run index cho WP-02.
- [x] MIG-03b: Thêm race/current-version constraints cho các schema ở WP sau.
- [x] MIG-04a: Viết upgrade check từ PostgreSQL database trống.
- [ ] MIG-04b: Bổ sung upgrade check từ revision trước khi có feature revision tiếp theo.
- [x] MIG-05: Ghi rollback/backup policy; restore drill dùng DB riêng.

## Điều kiện hoàn thành

- [x] Upgrade tới head tái lập được trên DB test.
- [x] Constraints race-critical tồn tại sau upgrade.
- [x] Không đổi schema ngoài migrations hoặc chạy destructive reset trên runtime DB.
