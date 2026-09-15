# CI — kiểm tra chất lượng không cần API trả phí

Trạng thái: CI foundation WP-01 đã có; integration/E2E/eval jobs được bổ sung theo các WP sau.
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
- [ ] CI-02: Chạy unit + API/MCP contract, migration upgrade và integration với service containers.
- [ ] CI-03: Thêm browser E2E khi có UI, phân nhóm job để lỗi dễ xác định.
- [ ] CI-04: Kiểm tra liên kết kế hoạch, schema seed/eval và secret scanning phù hợp.
- [ ] CI-05: Upload report/trace đã lọc khi fail; đặt timeout và quyền workflow tối thiểu.

## Điều kiện hoàn thành

- [ ] PR checks không dùng mạng model trả phí và fail đúng khi contract/security regression.
- [ ] Fresh dependency install, migrations và app build được kiểm tra, không có test rỗng báo pass giả.
