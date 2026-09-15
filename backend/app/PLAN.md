# Composition root và cấu hình

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-01, WP-02, WP-03.
Nguồn: [kế hoạch tổng](../../plan.md), mục 5, 14, 20; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Lắp ghép module và quản lý vòng đời tài nguyên của ứng dụng.

## Hợp đồng và trách nhiệm

- App factory tạo FastAPI và gắn router, exception mapping, request IDs.
- Async clients được tạo trong đúng process/event loop; không dùng client tạo trước Celery fork.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `main.py`
- `config.py`
- `dependencies.py`

## Phụ thuộc và phối hợp

- [backend/app/api](api/PLAN.md)
- [backend/app/db](db/PLAN.md)
- [backend/app/providers](providers/PLAN.md)
- [backend/app/jobs](jobs/PLAN.md)

## Các bước triển khai

- [ ] APP-01: Định nghĩa settings cho DB, Redis, provider, observability và limits theo kế hoạch tổng.
- [ ] APP-02: Tạo dependency factories và lifecycle đóng HTTP/DB/Redis clients.
- [ ] APP-03: Gắn error envelope, logging middleware, auth context và health routes.
- [ ] APP-04: Tách composition của API, job và MCP để service không import entrypoint.

## Điều kiện hoàn thành

- [ ] Import module không có side effects.
- [ ] Health/live chỉ đo process; health/ready kiểm tra DB/Redis, không gọi LLM.
- [ ] Có thể dựng app với fake dependencies trong tests.
