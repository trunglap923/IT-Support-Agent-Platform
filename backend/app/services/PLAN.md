# Business services

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-02, WP-07, WP-08, WP-11, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 3, 11, 13, 14; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Tập trung quy tắc nghiệp vụ và transaction dùng chung bởi HTTP, job và MCP.

## Hợp đồng và trách nhiệm

- Nhận principal và validated command; trả typed DTO/domain error.
- Services có quyền kiểm tra nghiệp vụ; adapters không tự sửa DB để bỏ qua policy.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `conversations/`
- `approvals/`
- `tickets/`
- `documents/`
- `budget/`
- `service_status/`

## Phụ thuộc và phối hợp

- [backend/app/services/conversations](conversations/PLAN.md)
- [backend/app/services/approvals](approvals/PLAN.md)
- [backend/app/services/tickets](tickets/PLAN.md)
- [backend/app/services/documents](documents/PLAN.md)
- [backend/app/services/budget](budget/PLAN.md)
- [backend/app/services/service_status](service_status/PLAN.md)

## Các bước triển khai

- [ ] SVC-01: Xây conversation/run service trước để có nền chat/job.
- [ ] SVC-02: Xây read business services trước các write workflows.
- [ ] SVC-03: Đặt transaction boundaries cho approval/ticket/publish và usage reservation.
- [ ] SVC-04: Tách error code nghiệp vụ khỏi HTTP status, dùng chung audit conventions.

## Điều kiện hoàn thành

- [ ] Không import router, browser hoặc LangGraph để thực hiện business rules.
- [ ] HTTP/MCP/job paths đi qua cùng quyền/ownership checks.
- [ ] Write effects và audit cần atomic được commit cùng transaction.
