# UI — quản lý trí nhớ có đồng ý

Trạng thái: hoàn thành cho WP-12.
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

- [x] UIMEM-01: Tạo consent/toggle với mô tả dữ liệu có thể lưu và giới hạn.
- [x] UIMEM-02: Hiển thị pending/active; hỗ trợ confirm/correct/delete và chọn thiết bị.
- [x] UIMEM-03: Xử lý xóa một mục và refresh từ server, không optimistic để lại fact đã xóa.
- [x] UIMEM-04: Giải thích rõ tắt memory không xóa dữ liệu và chỉ fact xác nhận mới được dùng.

## Điều kiện hoàn thành

- [x] Tắt/xóa trong lúc background job chạy không làm fact cũ xuất hiện lại.
- [x] Xóa một fact giữ các fact khác; bật lại chỉ dùng fact hợp lệ.
- [x] API chỉ truy vấn memory theo principal hiện tại; admin không có quyền xem thay owner.
