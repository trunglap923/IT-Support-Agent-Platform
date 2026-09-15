# Integration và failure tests

Trạng thái: migration, identity, auth/CSRF và conversation ownership tests WP-02 đã có; failure suites các WP sau chưa triển khai.
Work packages: WP-02, WP-03, WP-05, WP-08, WP-10, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 19.1, 19.4; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Kiểm tra transaction, queries, HTTP và recovery với PostgreSQL/Redis thật.

## Hợp đồng và trách nhiệm

- Database và Redis test riêng; provider fake để kiểm soát response/cost.
- Race tests dùng hai connections/tasks độc lập; không mô phỏng unique constraint bằng mock.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `test_auth_api.py`
- `test_scoped_retrieval.py`
- `test_approval_races.py`
- `test_job_recovery.py`
- `test_memory_races.py`
- `test_document_publish.py`

## Phụ thuộc và phối hợp

- [backend/migrations](../../migrations/PLAN.md)
- [backend/app/jobs](../../app/jobs/PLAN.md)
- [backend/app/services/tickets](../../app/services/tickets/PLAN.md)
- [backend/app/memory](../../app/memory/PLAN.md)
- [infra](../../../infra/PLAN.md)

## Các bước triển khai

- [x] INT-01: Upgrade migrations trên database tạm và seed minimal identity fixtures.
- [x] INT-02a: Test session/CSRF/RBAC và conversation/run ownership ở API/repository/DB.
- [ ] INT-02b: Test ACL source download, history và SSE khi endpoints được triển khai.
- [ ] INT-03: Test duplicate approve, worker crash sau commit và receipt recovery.
- [ ] INT-04: Test Redis enqueue race, stale jobs, checkpoint resume.
- [ ] INT-05: Test publish/ACL change trong run và delete memory trong extraction.

## Điều kiện hoàn thành

- [ ] Không lộ cross-user/department data trong regressions.
- [ ] Một approval đúng một ticket dưới concurrency và retry.
- [ ] Cleanup tests chỉ tác động resources của suite.
