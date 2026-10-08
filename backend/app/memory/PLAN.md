# Memory qua nhiều cuộc trò chuyện

Trạng thái: hoàn thành cho WP-12.
Work packages: WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 12, 17.2, 19; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Lưu fact được xác nhận theo thiết bị và lịch sử sự cố đúng owner.

## Hợp đồng và trách nhiệm

- Memory luôn chạy; pending candidates vẫn cần người dùng xác nhận trước khi thành fact.
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
- [x] MEM-03: Implement accept/reject/edit revision, TTL pending 7 ngày/active 90 ngày.
- [x] MEM-04: Implement delete/edit cùng epoch update; kiểm tra lại epoch trước commit.
- [x] MEM-05: Retrieve tối đa năm fact đã xác nhận theo owner/device vào LangGraph context.
- [x] MEM-06: Ghi embedding cho semantic assertion, incident episode và procedure version mới.
- [x] MEM-07: Hybrid retrieval kết hợp BM25, cosine, exact metadata, recency, confidence và authority.
- [x] MEM-08: Dùng chung một query embedding cho các memory lane trong mỗi agent run.
- [x] MEM-09: Lưu model/dimension cùng vector, bỏ qua vector khác embedding space và hỗ trợ backfill.

Sau khi migrate một database đã có memory, kiểm tra và backfill vector bằng:

```bash
make memory-reindex-dry-run
make memory-reindex
```

Nếu `EMBEDDING_PROVIDER=openai`, lệnh apply yêu cầu `RUN_PAID_REINDEX=1`.

## Điều kiện hoàn thành

- [x] Integration test xác nhận fact đi qua conversation và OS của hai thiết bị không bị trộn.
- [x] Delete trong lúc extraction chạy làm job cũ bị discard theo epoch.
- [x] Extractor chỉ nhận key allowlist; role/permission/instruction không trở thành memory.
