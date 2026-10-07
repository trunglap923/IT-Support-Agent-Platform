# Context và compaction

Trạng thái: unified Context Manager đã được nối vào LangGraph và OpenAI Agents runtime.
Work packages: WP-06, WP-12.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 8.3, 9.3, 12.4; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Ghép lịch sử, evidence và memory trong ngân sách token mà vẫn giữ nguồn gốc.

## Hợp đồng và trách nhiệm

- Nhận principal, current message, structured issue state, sources và confirmed memories.
- Trả model input có tool-call/result pairing hợp lệ và source/memory IDs.
- Budget theo model/call purpose; mặc định 16.000 context tokens, reserve output, safety margin
  và 15% cho system/tool schemas do provider sở hữu.

## Thành phần

- `adapters.py`: chuyển history, confirmed memory, working memory, observation và RAG evidence
  thành `ContextCandidate` có scope/provenance.
- `manager.py`: hard filter, conflict resolution, utility score, lane budget, borrowing và
  deterministic compaction.
- `runtime.py`: refresh working memory trước model call, persist audit metadata và summary artifact
  có retention ngắn.
- `builder.py`: adapter cũ cho các caller chưa chuyển đổi; runtime production không ghép history
  trực tiếp qua adapter này nữa.

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
- [x] CTX-07: Dùng chung candidate policy cho LangGraph và OpenAI Agents SDK.
- [x] CTX-08: Tách budget theo purpose/lane; hỗ trợ borrowing trong global hard limit.
- [x] CTX-09: Persist selection reason, hash, token metrics và addressable summary artifact.
- [x] CTX-10: Có endpoint explain owner-scoped cho IT/Admin, không trả raw context.
- [x] CTX-11: Loại context sai owner/department/namespace, restricted và stored prompt injection.

## Điều kiện hoàn thành

- [x] Conversation dài vẫn giữ current query và các bước đã xác nhận.
- [x] ACL thu hồi làm source text biến mất khỏi context/history được đọc lại.
- [x] Xóa một memory không làm mất các active fact hợp lệ khác.
