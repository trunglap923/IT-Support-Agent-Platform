# Frontend — composition và router

Trạng thái: composition, auth bootstrap/guard và cache reset WP-02 đã có; navigation theo role và feature routes thuộc WP sau.
Work packages: WP-01, WP-02, WP-06, WP-09.
Nguồn: [kế hoạch tổng](../../plan.md), mục 7, 14, 20; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Tập trung wiring ứng dụng, giữ nghiệp vụ trong từng feature.

## Hợp đồng và trách nhiệm

- Router theo mục 7: /login, /chat, /chat/:id, /tickets, /tickets/:id, /it/tickets, /admin/documents, /admin/services, /settings/memory.
- Documents và services dành cho admin; ticket có góc nhìn cá nhân/IT đúng role.
- Guard trên UI chỉ là tiện ích; backend vẫn kiểm tra mọi quyền.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `main.tsx`
- `App.tsx`
- `router.tsx`
- `providers.tsx`
- `styles.css`

## Phụ thuộc và phối hợp

- [frontend/src/api](api/PLAN.md)
- [frontend/src/components](components/PLAN.md)
- [frontend/src/features](features/PLAN.md)

## Các bước triển khai

- [x] WEB-01a: Khởi tạo QueryClient và auth bootstrap từ /auth/me.
- [x] WEB-01b: Thêm application error boundary không hiển thị raw exception.
- [x] WEB-02: Dựng navigation theo role, fallback 404 và loading ban đầu.
- [x] WEB-03: Reset query cache khi logout/đổi tài khoản để không giữ dữ liệu người trước.
- [x] WEB-04: Kết nối auth/chat/ticket/operations/document/memory theo feature routes, không thêm global store.

## Điều kiện hoàn thành

- [x] Reload deep link được proxy SPA xử lý; session hết hạn phát global event và guard đưa về login.
- [x] Logout, đổi user hoặc session hết hạn đều xóa toàn bộ React Query cache riêng tư.
