# Contract tests

Trạng thái: MCP stdio và governed tool registry/executor contracts WP-07 đã triển khai.
Work packages: WP-01, WP-06, WP-07, WP-08.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 10, 14, 16, 19.1; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Kiểm tra giao diện giữa provider, tool registry, MCP và HTTP DTO.

## Hợp đồng và trách nhiệm

- MCP test khởi chạy stdio subprocess thật với test actor/run context.
- Provider fixtures mô phỏng protocol/tool call pairing; paid smoke là lệnh riêng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `test_provider_contract.py`
- `test_mcp_contract.py`
- `test_openapi_contract.py`
- `test_tool_schema.py`

## Phụ thuộc và phối hợp

- [backend/app/providers](../../app/providers/PLAN.md)
- [backend/app/tools](../../app/tools/PLAN.md)
- [backend/app/mcp_server](../../app/mcp_server/PLAN.md)
- [frontend/src/api](../../../frontend/src/api/PLAN.md)

## Các bước triển khai

- [x] CTR-01: So khớp discovery hai MCP read tools với registry bốn model capabilities và schema đã pin.
- [x] CTR-02: Kiểm tra strict schema, extra forbidden fields và result envelope.
- [x] CTR-03: Test MCP context thiếu/sai owner, actor isolation và stdout protocol.
- [ ] CTR-04: Kiểm tra OpenAPI response models đủ để frontend generate types.

## Điều kiện hoàn thành

- [x] Schema drift giữa MCP read discovery và registry khiến contract test fail.
- [x] Tool call/result IDs được giữ đúng; wrong args không đến business write.
