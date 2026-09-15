# ADR — quyết định kiến trúc và kết quả thử tích hợp

Trạng thái: ADR-0001 và ADR-0002 compatibility M0 đã hoàn thành; các quyết định nghiệp vụ sau vẫn mở.
Work packages: WP-01, WP-06, WP-08, WP-12, WP-14.
Nguồn: [kế hoạch tổng](../../plan.md), mục 5, 9, 10, 11, 12, 20; [thứ tự triển khai](../implementation-roadmap.md).

## Mục tiêu

Lưu lý do chọn thiết kế, tradeoff và bằng chứng spike để không quyết định lại trong từng module.

## Hợp đồng và trách nhiệm

- Mỗi ADR ghi status/date/context/decision/consequences và liên kết test/spike khi có.
- Quyết định thiết kế đã chọn không đồng nghĩa các integration đã thử thành công.
- Không mở rộng V1 sang multi-agent/public MCP/multi-tenant nếu chưa cập nhật scope với người xây dựng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `0001-project-structure.md`
- `0002-runtime-and-integration.md`
- `0003-approval-and-recovery.md`
- `0004-memory-lifecycle.md`

## Phụ thuộc và phối hợp

- [backend/app/providers](../../backend/app/providers/PLAN.md)
- [backend/app/mcp_server](../../backend/app/mcp_server/PLAN.md)
- [backend/app/agent](../../backend/app/agent/PLAN.md)
- [backend/app/memory](../../backend/app/memory/PLAN.md)

## Các bước triển khai

- [x] ADR-01: Ghi ADR cấu trúc repo và quy tắc dependency direction.
- [x] ADR-02a: Ghi contract Responses offline, MCP stdio/actor isolation và PostgreSQL checkpoint/resume cùng phiên bản đã kiểm tra.
- [x] ADR-02b: Chạy Responses live bằng opt-in/account có quota và bổ sung kết quả.
- [ ] ADR-03: Ghi ADR transaction/receipt/lock boundary trước hoàn tất WP-08.
- [ ] ADR-04: Ghi ADR consent/epoch/retention trước hoàn tất WP-12; đánh dấu quyết định cũ superseded nếu thay.

## Điều kiện hoàn thành

- [x] Các spike nền tảng có kết quả thật trước khi đánh dấu M0 hoàn thành.
- [ ] Mỗi thay đổi ảnh hưởng nhiều module có nguồn quyết định duy nhất.
