# Integration và failure tests

Trạng thái: WP-02/03 integration và WP-08/10 approval, ticket, lease/recovery failure suites đã triển khai.
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
- [x] INT-02b: Test SSE ownership, cursor/reconnect và không tạo thêm run khi đọc lại.
- [x] INT-02c: Test readiness PostgreSQL/Redis và login rate limit/fail-closed với Redis thật.
- [x] INT-03: Test duplicate approve, worker crash sau commit và receipt recovery.
- [x] INT-04a: Test commit/enqueue race, duplicate worker claim và delivery qua Redis thật.
- [x] INT-04b: Test stale lease, crash recovery và checkpoint resume đầy đủ ở WP-10.
- [x] INT-05: Document lifecycle test recheck ACL/revoke trên retrieval/history/source; memory concurrency discard extraction theo epoch sau delete.

## Điều kiện hoàn thành

- [x] Không lộ cross-user/department data trong regressions WP-02–WP-10.
- [x] Một approval đúng một ticket dưới concurrency và retry.
- [x] Cleanup tests chỉ tác động database/Redis resources do suite tạo.
