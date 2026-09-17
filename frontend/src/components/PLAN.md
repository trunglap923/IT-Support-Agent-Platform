# Frontend — thành phần dùng chung

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-01, WP-06, WP-09, WP-11, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 7, 17; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Dùng lại những thành phần thực sự chung giữa các trang mà không xây design system lớn.

## Hợp đồng và trách nhiệm

- Render Markdown không chạy raw HTML/script; link ngoài có thuộc tính an toàn.
- Badge phân biệt simulated service status, ticket status và run status.
- Dialog thường chỉ điều khiển UI; approval nghiệp vụ luôn qua API riêng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `AppLayout.tsx`
- `AsyncState.tsx`
- `ConfirmDialog.tsx`
- `StatusBadge.tsx`
- `SafeMarkdown.tsx`

## Phụ thuộc và phối hợp

- [frontend/src/api](../api/PLAN.md)
- [frontend/e2e](../../e2e/PLAN.md)

## Các bước triển khai

- [ ] UI-01: Dựng layout, navigation, form field, empty/error state khi feature đầu tiên cần.
- [ ] UI-02: Citation link chỉ mở authenticated server URL đã có; SafeMarkdown còn thiếu vì answer đang render plain text.
- [ ] UI-03: Thiết lập dialog với focus trap, nhãn rõ ràng và keyboard navigation.
- [ ] UI-04: Giữ thông báo lỗi dễ hiểu bằng tiếng Việt; không hiển thị raw exception/secret.

## Điều kiện hoàn thành

- [ ] Payload Markdown/HTML độc hại không thực thi.
- [ ] Loading/disabled/error có nhãn đọc được; không tái dùng dialog thường để bỏ qua approval.
