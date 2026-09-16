# Registry token policy

## Thời hạn

Token người dùng có thời hạn tối đa 8 giờ. Hãy tạo token mới khi bắt đầu phiên làm việc và
thu hồi token ngay khi nghi ngờ bị lộ.

## Scope

Chỉ cấp scope pull hoặc push cần thiết cho repository cụ thể. Không cấp quyền quản trị cho
token dùng trong máy cá nhân.

## Storage

Không commit token vào Git, image, `.env` dùng chung hoặc ticket hỗ trợ.
