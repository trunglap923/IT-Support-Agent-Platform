# Business services

Trạng thái: conversation, read services và transactional write services đã triển khai; error taxonomy/audit conventions còn hoàn thiện.
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

- [x] SVC-01: Conversation/run submission, state, lease và feedback services đã có.
- [x] SVC-02: Ticket/service/document/memory read services áp scope trong SQL.
- [x] SVC-03: Approval/ticket/publish và usage reservation có transaction boundaries cùng event/receipt.
- [ ] SVC-04: Tách error code nghiệp vụ khỏi HTTP status, dùng chung audit conventions.

## Điều kiện hoàn thành

- [x] Business services không import router, browser hoặc LangGraph để thực hiện quy tắc.
- [ ] HTTP/MCP/job paths đi qua cùng quyền/ownership checks.
- [ ] Write effects và audit cần atomic được commit cùng transaction.
