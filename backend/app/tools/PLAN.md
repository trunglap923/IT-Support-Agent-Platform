# Tool schema, registry và executor

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-06, WP-07, WP-08.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 9, 10, 11; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp đúng bốn capabilities cho model và kiểm soát execution.

## Hợp đồng và trách nhiệm

- Model tools: search_knowledge_base, check_service_status, get_my_open_tickets, create_ticket.
- RAG chạy local; ba business tools qua MCP.
- create_ticket là đề xuất; executor chỉ dispatch write sau approval.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `schemas.py`
- `registry.py`
- `executor.py`
- `results.py`

## Phụ thuộc và phối hợp

- [backend/app/auth](../auth/PLAN.md)
- [backend/app/rag](../rag/PLAN.md)
- [backend/app/mcp_server](../mcp_server/PLAN.md)
- [backend/app/services/approvals](../services/approvals/PLAN.md)
- [backend/tests/contract](../../tests/contract/PLAN.md)

## Các bước triển khai

- [ ] TOOL-01: Định nghĩa strict schemas với extra=forbid, enum và length limits.
- [ ] TOOL-02: Inject actor/run/approval từ trusted context, ngoài schema model.
- [ ] TOOL-03: Dispatch RAG/MCP qua allowlist và kiểm tra quyền trước mỗi execution.
- [ ] TOOL-04: Giới hạn timeout, retries, repeated arguments và result size.
- [ ] TOOL-05: Ghi tool_calls, validate envelope success/failed/unknown và giữ call_id pairing.

## Điều kiện hoàn thành

- [ ] Model không truyền được user_id/role/SQL/token/approval flag.
- [ ] Wrong-owner device hoặc arguments thừa bị chặn trước side effect.
- [ ] Tool receipt có nguồn từ service; text của model không đổi trạng thái ticket.
