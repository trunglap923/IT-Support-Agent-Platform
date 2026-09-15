# Backend Python

Trạng thái: WP-01 đã kiểm tra local; backend DB/auth/persistence WP-02 đã triển khai và chờ integration gate cuối.
Work packages: WP-01, WP-02.
Nguồn: [kế hoạch tổng](../plan.md), mục 5, 20, 21; [thứ tự triển khai](../docs/implementation-roadmap.md).

## Mục tiêu

Khởi tạo package Python dùng chung cho FastAPI, workers và MCP subprocess.

## Hợp đồng và trách nhiệm

- Python 3.12; cấu hình runtime từ environment, secrets không đi vào frontend.
- API/worker/MCP là entrypoint riêng của cùng package; module nghiệp vụ không phụ thuộc HTTP.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `pyproject.toml`
- `uv.lock`
- `app/main.py`
- `app/config.py`

## Phụ thuộc và phối hợp

- [backend/app](app/PLAN.md)
- [backend/migrations](migrations/PLAN.md)
- [infra](../infra/PLAN.md)
- [.github/workflows](../.github/workflows/PLAN.md)

## Các bước triển khai

- [x] BE-01: Tạo project metadata, nhóm runtime/dev dependencies và lock sau compatibility spike.
- [x] BE-02: Tạo app factory, lifespan và config validation; phân biệt fake-provider và live modes.
- [x] BE-03a: Nối database/auth theo dependency injection và dùng migration URL riêng.
- [ ] BE-03b: Nối worker/services các WP sau và tách DB roles production ở WP-14.
- [x] BE-04: Cung cấp lệnh lint/type-check/test từ root khi toolchain đã cài.

## Điều kiện hoàn thành

- [x] Import package không gọi mạng, không connect DB và không spawn MCP.
- [x] Fresh install dùng lockfile tái lập được; config sai có thông báo rõ.
- [ ] Chỉ đánh dấu WP-01 xong sau khi frontend/backend install/build và CI smoke tests đạt.
