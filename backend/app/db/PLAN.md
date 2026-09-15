# Schema và DB sessions

Trạng thái: async engine/session và identity/session/conversation/run/event models WP-02 đã có; schema các WP sau chưa triển khai.
Work packages: WP-02, WP-03, WP-04, WP-07, WP-08, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 13; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Chuyển schema tổng thành SQLAlchemy models và cơ chế session có vòng đời rõ.

## Hợp đồng và trách nhiệm

- PostgreSQL 17 + pgvector, UUID IDs, UTC timestamps, integer version.
- Schema chi tiết là mục 13 của plan.md; checkpoint storage nằm schema riêng.
- App role không DDL; migrations dùng credential riêng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `models.py`
- `base.py`
- `session.py`
- `types.py`

## Phụ thuộc và phối hợp

- [backend/migrations](../../migrations/PLAN.md)
- [backend/app/repositories](../repositories/PLAN.md)
- [backend/tests/integration](../../tests/integration/PLAN.md)

## Các bước triển khai

- [x] DB-01a: Tạo department/user identity models với UUID, role và password hash.
- [x] DB-01b: Tạo conversation/message/run/event models.
- [ ] DB-01c: Tạo device model khi thêm device API/seed.
- [ ] DB-02: Thêm document/version/chunk với vector(1536), ownership và composite version constraint.
- [ ] DB-03: Thêm usage ledger trước paid call WP-04; ticket/service_states/audit ở WP-07, approval constraints WP-08 và memory/jobs WP-12; system_state cùng document versioning.
- [x] DB-04a: Định nghĩa unique request và partial index cho active run.
- [ ] DB-04b: Thêm constraints cho action, receipt, memory và ingestion ở WP tương ứng.
- [x] DB-05a: Tạo async engine/session factory theo process/event loop, không dùng global connection.
- [ ] DB-05b: Quyết định delete/retain FK behavior theo retention khi thêm models.

## Điều kiện hoàn thành

- [ ] Migrations fresh database tạo đúng constraints/indexes.
- [ ] Race insert bị chặn bởi DB, không chỉ Python check.
- [ ] App startup/worker fork không reuse connection không hợp lệ.
