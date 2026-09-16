# CI — kiểm tra chất lượng không cần API trả phí

Trạng thái: pipeline release verification đã tách migration, integration, contracts, E2E, images và secret scan; chờ lần chạy GitHub Actions đầu tiên.
Work packages: WP-01, WP-03, WP-09, WP-13, WP-14.
Nguồn: [kế hoạch tổng](../../plan.md), mục 19, 20, 22; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Chặn lỗi cơ bản, contract và các đường an toàn trước khi gộp thay đổi.

## Hợp đồng và trách nhiệm

- CI mặc định fake provider, PostgreSQL/pgvector + Redis test riêng; không có OpenAI/Langfuse key.
- Backend install từ uv.lock; frontend npm ci từ package-lock.json.
- Live model eval là thao tác opt-in có quota, không chạy tự động ở PR không tin cậy.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `ci.yml`

## Phụ thuộc và phối hợp

- [backend/tests](../../backend/tests/PLAN.md)
- [frontend/e2e](../../frontend/e2e/PLAN.md)
- [evals/runner](../../evals/runner/PLAN.md)
- [infra](../../infra/PLAN.md)

## Các bước triển khai

- [x] CI-01: Thêm lint/typecheck/format checks backend và frontend sau WP-01.
- [x] CI-02a: Chạy unit + API/MCP contract, migration upgrade và integration với PostgreSQL/pgvector.
- [x] CI-02b: Thêm Redis service, broker delivery test và fake-mode run integration ở WP-03.
- [x] CI-03: Browser E2E có job riêng; backend unit/contracts/migration/integration và frontend được phân nhóm.
- [x] CI-04: Kiểm tra schema evaluation/reproducibility và scan credential pattern trên tracked files.
- [x] CI-05: Upload JUnit/trace/build log chỉ khi fail; mọi job có timeout và workflow chỉ có `contents: read`.

## Điều kiện hoàn thành

- [x] Workflow không nhận paid API key, ép fake provider và có contract/security regression jobs rõ ràng.
- [x] Fresh locked dependency install, clean migration và cả hai production image build đều là required workflow jobs.

Local validation chỉ xác nhận syntax, command và cùng test suite; trạng thái GitHub-hosted vẫn phải chờ workflow chạy sau push, không được tính là bằng chứng remote pass.
