# UI — quản lý trí nhớ có đồng ý

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-12.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 4, 7, 12, 14, 17; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Người dùng hiểu điều gì được lưu và tự quyết định bật, xác nhận, sửa hoặc xóa.

## Hợp đồng và trách nhiệm

- Memory tắt mặc định; fact đề xuất phải xác nhận trước khi dùng ở conversation mới.
- Fact theo thiết bị, có nguồn/thời hạn; chỉ hiển thị danh sách của chính user.
- Tắt memory không đồng nghĩa xóa: diễn giải rõ và cung cấp xóa riêng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `MemoryPage.tsx`
- `MemoryConsent.tsx`
- `PendingFactCard.tsx`
- `DeviceSelector.tsx`
- `MemoryList.tsx`

## Phụ thuộc và phối hợp

- [backend/app/memory](../../../../backend/app/memory/PLAN.md)
- [frontend/src/features/chat](../chat/PLAN.md)
- [frontend/src/api](../../api/PLAN.md)

## Các bước triển khai

- [ ] UIMEM-01: Tạo consent/toggle với mô tả dữ liệu có thể lưu và giới hạn.
- [ ] UIMEM-02: Hiển thị pending/active/expired; hỗ trợ confirm/correct/delete và chọn thiết bị.
- [ ] UIMEM-03: Xử lý yêu cầu xóa một/all và cập nhật UI theo server, không optimistic để lại fact đã xóa.
- [ ] UIMEM-04: Tạo hướng dẫn demo hai cuộc trò chuyện và đảm bảo không hứa sẽ nhớ khi consent tắt.

## Điều kiện hoàn thành

- [ ] Tắt/xóa trong lúc background job chạy không làm fact cũ xuất hiện lại.
- [ ] Xóa một fact giữ các fact khác; bật lại chỉ dùng fact hợp lệ.
- [ ] User khác và admin không xem memory riêng của người này.
