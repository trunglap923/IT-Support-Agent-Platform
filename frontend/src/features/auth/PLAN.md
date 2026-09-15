# UI — đăng nhập và phiên người dùng

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
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

- [ ] UIAUTH-01: Tạo form login và thông báo credential sai/rate limited.
- [ ] UIAUTH-02: Bootstrap session + CSRF; hiển thị role/phòng ban để demo ACL.
- [ ] UIAUTH-03: Đăng xuất và xóa toàn bộ cache chứa dữ liệu riêng.
- [ ] UIAUTH-04: Xử lý session hết hạn khi đang chat hoặc xác nhận draft.

## Điều kiện hoàn thành

- [ ] User chưa login không xem được trang riêng.
- [ ] Logout rồi login user khác không hiện dữ liệu cũ; lỗi quyền không bị UI che thành thành công.
