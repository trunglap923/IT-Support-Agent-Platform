# Frontend — ứng dụng web demo

Trạng thái: foundation WP-01 đã triển khai và kiểm tra; feature chat/ticket/docs/memory còn theo WP sau.
Work packages: WP-01, WP-06, WP-09, WP-11, WP-12.
Nguồn: [kế hoạch tổng](../plan.md), mục 5, 7, 14, 20, 21; [thứ tự triển khai](../docs/implementation-roadmap.md).

## Mục tiêu

Có web tiếng Việt để demo toàn bộ luồng, làm chat tối thiểu từ M2 trước khi hoàn thiện các trang quản trị.

## Hợp đồng và trách nhiệm

- React + TypeScript + Vite; React Router, TanStack Query, Tailwind theo kế hoạch tổng.
- Frontend gọi API cùng origin; không chứa OpenAI/Langfuse secret hoặc tự quyết định quyền nghiệp vụ.
- WP-01 tạo shell; WP-06 có chat/RAG demo sớm; WP-09 bổ sung approval và ticket.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `package.json`
- `package-lock.json`
- `tsconfig.json`
- `vite.config.ts`
- `index.html`

## Phụ thuộc và phối hợp

- [frontend/src](src/PLAN.md)
- [frontend/e2e](e2e/PLAN.md)
- [infra](../infra/PLAN.md)

## Các bước triển khai

- [x] FE-01: Chốt Node LTS và bộ dependency tương thích, khóa bằng package-lock.json.
- [x] FE-02: Thiết lập dev/build/typecheck/lint và proxy /api; phân biệt cấu hình dev/production.
- [x] FE-03: Dựng shell/router và màn hình đăng nhập; tích hợp từng feature khi backend tương ứng sẵn sàng.
- [x] FE-04: Thêm trạng thái loading/empty/error, bàn phím và bố cục dùng được trên laptop/mobile.

## Điều kiện hoàn thành

- [x] Cài lại bằng npm ci, typecheck/lint/build thành công khi triển khai WP-01.
- [ ] Không có secret trong bundle; refresh đường dẫn SPA và SSE qua proxy hoạt động.
