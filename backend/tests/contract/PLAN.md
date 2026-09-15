# Contract tests

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
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

- [ ] CTR-01: So khớp discovery ba business tools với allowlist và schema đã pin.
- [ ] CTR-02: Kiểm tra strict schema, extra forbidden fields và result envelope.
- [ ] CTR-03: Test MCP context thiếu/sai owner và logging không phá stdout.
- [ ] CTR-04: Kiểm tra OpenAPI response models đủ để frontend generate types.

## Điều kiện hoàn thành

- [ ] Schema drift khiến test fail trước khi deploy.
- [ ] Tool call/result IDs được giữ đúng; wrong args không đến business write.
