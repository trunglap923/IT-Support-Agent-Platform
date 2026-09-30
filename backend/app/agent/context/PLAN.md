# Context và compaction

Trạng thái: context contract, bounded history, extractive summary và confirmed memory theo device đã có.
Work packages: WP-06, WP-12.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 8.3, 9.3, 12.4; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Ghép lịch sử, evidence và memory trong ngân sách token mà vẫn giữ nguồn gốc.

## Hợp đồng và trách nhiệm

- Nhận principal, current message, structured issue state, sources và confirmed memories.
- Trả model input có tool-call/result pairing hợp lệ và source/memory IDs.
- Tối đa 10.000 input tokens/call; phân bổ cụ thể theo mục 12.4.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `builder.py`
- `budget.py`
- `summary.py`

## Phụ thuộc và phối hợp

- [backend/app/rag/citations](../../rag/citations/PLAN.md)
- [backend/app/memory](../../memory/PLAN.md)
- [backend/app/prompts](../../prompts/PLAN.md)
- [backend/app/auth](../../auth/PLAN.md)

## Các bước triển khai

- [x] CTX-01: Luôn giữ current query và lịch sử gần nhất trong contract serializable.
- [x] CTX-02: Giới hạn history/current query theo input-token budget; evidence/memory quota nối theo WP tương ứng.
- [x] CTX-03: Phân biệt suggested_steps với confirmed_attempted_steps khi tạo summary.
- [x] CTX-04: Loại sources/history nay trái quyền; label nguồn superseded là historical.
- [x] CTX-05: Đọc lại memory settings/epoch khi build; không hồi sinh dữ liệu từ checkpoint cũ.
- [x] CTX-06: Compact hội thoại dài thành summary có nhãn untrusted và giữ 12 message gần nhất.

## Điều kiện hoàn thành

- [x] Conversation dài vẫn giữ current query và các bước đã xác nhận.
- [x] ACL thu hồi làm source text biến mất khỏi context/history được đọc lại.
- [x] Xóa một memory không làm mất các active fact hợp lệ khác.
