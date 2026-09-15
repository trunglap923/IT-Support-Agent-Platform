# MCP server nội bộ

Trạng thái: spike stdio/actor isolation M0 đã đạt; business tools vẫn thuộc WP-07.
Work packages: WP-07, WP-08, WP-10.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 5.2, 10.3; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Expose status/ticket business tools qua một stdio server của ứng dụng.

## Hợp đồng và trách nhiệm

- Server subprocess riêng cho mỗi execution segment; argv/module cố định.
- Actor/run từ worker qua environment allowlist, đối chiếu DB mỗi call.
- Không có public endpoint; stdio context không được quảng bá là OAuth authentication.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `__main__.py`
- `server.py`
- `context.py`
- `status_tools.py`
- `ticket_tools.py`

## Phụ thuộc và phối hợp

- [backend/app/tools](../tools/PLAN.md)
- [backend/app/services/tickets](../services/tickets/PLAN.md)
- [backend/app/services/service_status](../services/service_status/PLAN.md)
- [backend/app/services/approvals](../services/approvals/PLAN.md)
- [backend/tests/contract](../../tests/contract/PLAN.md)

## Các bước triển khai

- [ ] MCP-01: Khóa SDK version sau spike; khai báo ba business schemas theo registry.
- [ ] MCP-02: Tạo startup/shutdown và lấy current principal từ trusted actor/run.
- [ ] MCP-03: Nối status/ticket read services với owner filters.
- [ ] MCP-04: Nối approved write: đọc approval_id từ executor metadata, validate hash/expiry/owner.
- [ ] MCP-05: Chỉ ghi MCP messages ra stdout, safe logs ra stderr; đóng subprocess khi kết thúc hoặc timeout.

## Điều kiện hoàn thành

- [ ] Discovery đúng ba tên/schema; contract test gọi thật qua stdio.
- [ ] Thiếu actor/run hoặc sai run owner bị từ chối.
- [ ] Subprocess không nhận OpenAI/Langfuse keys; crash-after-commit tra receipt trước retry.

## Bằng chứng spike M0

- MCP Python SDK 2.2.0 được khóa trong `uv.lock`; spike sử dụng trực tiếp `MCPServer`,
  `Client` và `StdioServerParameters` của SDK hiện hành.
- Contract test khởi động đồng thời hai subprocess stdio, discovery/call
  `current_actor` và xác nhận actor/run khác nhau không bị trộn.
- Subprocess nhận environment allowlist; OpenAI/Langfuse/database credentials của process
  cha không xuất hiện. Đây chưa phải xác thực người dùng hoặc ba business tools WP-07.
