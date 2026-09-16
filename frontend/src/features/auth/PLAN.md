# UI — đăng nhập và phiên người dùng

Trạng thái: login/session/logout và route protection WP-02 đã triển khai.
Work packages: WP-02.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 3, 7, 14, 17; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Đăng nhập bằng tài khoản demo có role và phòng ban rõ ràng.

## Hợp đồng và trách nhiệm

- Session opaque HttpOnly do server quản lý; không lưu token đăng nhập trong localStorage.
- User/role/department lấy từ /auth/me; login demo chỉ dùng dữ liệu giả.
- Không làm đăng ký, quên mật khẩu hay SSO trong V1.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `LoginPage.tsx`
- `AuthProvider.tsx`
- `RequireAuth.tsx`
- `useAuth.ts`

## Phụ thuộc và phối hợp

- [backend/app/auth](../../../../backend/app/auth/PLAN.md)
- [frontend/src/api](../../api/PLAN.md)
- [data/seed](../../../../data/seed/PLAN.md)

## Các bước triển khai

- [x] UIAUTH-01a: Tạo form login và thông báo credential sai.
- [x] UIAUTH-01b: Hiển thị lỗi rate-limited riêng khi backend trả `429`.
- [x] UIAUTH-02: Bootstrap session + CSRF; hiển thị role/phòng ban để demo ACL.
- [x] UIAUTH-03: Đăng xuất và xóa toàn bộ cache chứa dữ liệu riêng.
- [x] UIAUTH-04a: Session hết hạn khi bootstrap chuyển về login.
- [ ] UIAUTH-04b: Xử lý session hết hạn giữa chat/approval khi các feature đó tồn tại.

## Điều kiện hoàn thành

- [x] User chưa login không xem được trang riêng qua `RequireAuth`.
- [x] Logout xóa React Query cache và auth state; lỗi login/CSRF được hiển thị, không giả thành công.
