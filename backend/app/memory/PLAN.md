# Memory qua nhiều cuộc trò chuyện

Trạng thái: P53/P54 hoàn thành; P55 đang chờ.
Work packages: WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 12, 17.2, 19; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Lưu fact được xác nhận theo thiết bị và lịch sử sự cố đúng owner.

## Hợp đồng và trách nhiệm

- Mặc định off; bật qua settings; pending candidates cần người dùng xác nhận.
- Fact active theo owner/device/key; episodic records tham chiếu ticket hiện tại.
- memory_epoch chặn job cũ; không loại mọi active fact còn giữ chỉ vì epoch tăng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `extractor.py`
- `lifecycle.py`
- `retrieval.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [backend/app/agent/context](../agent/context/PLAN.md)
- [backend/app/jobs](../jobs/PLAN.md)
- [backend/app/services/budget](../services/budget/PLAN.md)
- [backend/app/services/tickets](../services/tickets/PLAN.md)
- [frontend/src/features/memory](../../../frontend/src/features/memory/PLAN.md)

## Các bước triển khai

- [x] MEM-01: Định nghĩa allowlist OS/version/device label/language và provenance.
- [x] MEM-02: Extract chỉ user messages mới; deterministic fake extractor tạo pending candidate.
- [ ] MEM-03: Accept/reject và TTL pending 7 ngày/active 90 ngày đã có; edit ở P55.
- [ ] MEM-04: Implement toggle/delete cùng epoch update; kiểm tra lại consent/epoch trước commit.
- [x] MEM-05: Retrieve tối đa năm fact đã xác nhận theo owner/device vào LangGraph context.

## Điều kiện hoàn thành

- [ ] UC-06/11/12 pass; nhiều thiết bị không ghi đè OS nhau.
- [ ] Delete trong lúc extraction chạy không tái tạo mục đã xóa; xóa một mục giữ các mục khác.
- [ ] Không lấy role/permission/instruction từ memory; không tự quét ticket cũ để khôi phục memory đã xóa.
