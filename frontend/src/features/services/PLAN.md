# UI — trạng thái dịch vụ mô phỏng

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-07, WP-09.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 3, 4, 7, 10, 14; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Admin điều khiển kịch bản VPN/registry/GitLab cho demo lặp lại được.

## Hợp đồng và trách nhiệm

- Mọi trạng thái đều có nhãn MÔ PHỎNG; không khẳng định đã đo hạ tầng thật.
- Chỉ admin đổi trạng thái; người dùng hỏi thông tin qua chat/tool read.
- Service ids cố định từ seed; không nhận URL/command kết nối tùy ý.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `ServicesPage.tsx`
- `ServiceStatusForm.tsx`
- `queries.ts`

## Phụ thuộc và phối hợp

- [backend/app/services/service_status](../../../../backend/app/services/service_status/PLAN.md)
- [backend/app/mcp_server](../../../../backend/app/mcp_server/PLAN.md)
- [data/seed](../../../../data/seed/PLAN.md)

## Các bước triển khai

- [ ] UISIM-01: Hiển thị trạng thái, thông điệp và updated_at cho các dịch vụ trong seed.
- [ ] UISIM-02: Thêm form admin cập nhật theo enum/schema của backend.
- [ ] UISIM-03: Hiển thị xác nhận cập nhật thật và audit reference nếu API cung cấp.
- [ ] UISIM-04: Kiểm tra chat đọc giá trị mới sau admin update, không giữ cache sai.

## Điều kiện hoàn thành

- [ ] Kịch bản VPN outage có thể bật/tắt lại mà không sửa code.
- [ ] Employee/IT không sửa được service state dù gọi API trực tiếp.
