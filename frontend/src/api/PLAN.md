# Frontend — HTTP client và sự kiện run

Trạng thái: auth client tối thiểu WP-02 đã có; client dùng chung và run events thuộc WP-03.
Work packages: WP-02, WP-03, WP-06, WP-09.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 7, 9, 14, 15; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp client có kiểu và reconnect an toàn cho tất cả feature.

## Hợp đồng và trách nhiệm

- Cookie session cùng origin; request ghi mang CSRF token theo auth contract.
- DTO/error code dựa trên OpenAPI backend; không định nghĩa một hợp đồng API khác.
- SSE phát workflow status và final response đã kiểm tra; reconnect không tạo run mới.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `client.ts`
- `types.ts`
- `query-keys.ts`
- `run-events.ts`

## Phụ thuộc và phối hợp

- [backend/app/api](../../../backend/app/api/PLAN.md)
- [backend/app/auth](../../../backend/app/auth/PLAN.md)
- [backend/app/services/conversations](../../../backend/app/services/conversations/PLAN.md)

## Các bước triển khai

- [ ] HTTPUI-01: Tạo fetch wrapper với abort timeout, error envelope và xử lý 401/403/409/429.
- [ ] HTTPUI-02: Chuẩn hóa query keys theo user/scope để invalidate và xóa khi logout.
- [ ] HTTPUI-03: Tạo run dùng client_request_id ổn định khi retry; đổi payload phải dùng id mới.
- [x] HTTPUI-04: Implement fetch SSE với event cursor/Last-Event-ID, bounded reconnect và GET run snapshot fallback.
- [ ] HTTPUI-05: Sinh hoặc kiểm tra TypeScript DTO từ OpenAPI bằng bước lặp lại được.

## Điều kiện hoàn thành

- [ ] Mạng gián đoạn/reconnect không nhân đôi message hoặc tạo ticket mới.
- [ ] Giới hạn retry; abort UI không tự suy thành cancel nghiệp vụ.
