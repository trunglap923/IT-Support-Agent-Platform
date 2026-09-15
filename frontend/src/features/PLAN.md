# Frontend — các khu vực chức năng

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-02, WP-06, WP-09, WP-11, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 4, 7, 21; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Chia UI theo nghiệp vụ để có thể hoàn thành và kiểm thử từng lát cắt.

## Hợp đồng và trách nhiệm

- Mỗi feature sở hữu page, component và query/mutation hooks của nó.
- Thứ tự: auth + chat tối thiểu → chat approval/tickets → documents → memory.
- Services là trang nhỏ cho admin đổi trạng thái giả lập phục vụ demo; không kết nối hệ thống thật.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `auth/`
- `chat/`
- `tickets/`
- `documents/`
- `memory/`
- `services/`

## Phụ thuộc và phối hợp

- [frontend/src/features/auth](auth/PLAN.md)
- [frontend/src/features/chat](chat/PLAN.md)
- [frontend/src/features/tickets](tickets/PLAN.md)
- [frontend/src/features/documents](documents/PLAN.md)
- [frontend/src/features/memory](memory/PLAN.md)
- [frontend/src/features/services](services/PLAN.md)

## Các bước triển khai

- [ ] FEATURE-01: Nối use case UC-01..UC-12 của kế hoạch tổng tới page tương ứng.
- [ ] FEATURE-02: Chỉ đưa component thực sự chia sẻ ra components/.
- [ ] FEATURE-03: Thống nhất invalidation sau approve, đổi ticket, publish tài liệu và xác nhận/xóa memory.
- [ ] FEATURE-04: Viết E2E theo hành trình người dùng xuyên các feature.

## Điều kiện hoàn thành

- [ ] Mọi use case V1 có UI hoặc luồng được nêu rõ trong test.
- [ ] Không có feature tự gọi model hoặc tự đọc DB.
