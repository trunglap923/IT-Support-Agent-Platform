# Tìm kiếm hybrid có phân quyền

Trạng thái: exact vector + FTS + scoped RRF baseline đã triển khai.
Work packages: WP-05, WP-13.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 8.2, 19; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Tìm evidence bằng vector và lexical search trong tập tài liệu user được đọc.

## Hợp đồng và trách nhiệm

- Input query + server principal; model không truyền SQL/ACL filters.
- Cosine exact top 20 + FTS ts_rank_cd top 20 → dedupe/RRF(k=60) → top 5.
- Reranker/HNSW tắt ban đầu; model space theo mục 16 của kế hoạch tổng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `query.py`
- `filters.py`
- `vector.py`
- `lexical.py`
- `fusion.py`

## Phụ thuộc và phối hợp

- [backend/app/auth](../../auth/PLAN.md)
- [backend/app/repositories](../../repositories/PLAN.md)
- [backend/app/providers](../../providers/PLAN.md)
- [backend/app/rag/citations](../citations/PLAN.md)
- [evals/runner](../../../../evals/runner/PLAN.md)

## Các bước triển khai

- [x] RET-01: Tạo predicate visibility/department/current version/archive/effective/expiry dùng chung hai nhánh search.
- [x] RET-02: Xây query embedding và PostgreSQL full-text query.
- [x] RET-03: Fuse ranks bằng RRF thay vì cộng score khác thang đo.
- [ ] RET-04: Đo Recall@5 trên cases answerable, tách no-answer cases.
- [ ] RET-05: Lưu corpus/config version vào trace và eval artifacts.

## Điều kiện hoàn thành

- [ ] Không trả title/snippet/chunk trái quyền tới context, logs hoặc UI.
- [ ] FTS và vector cùng scope; nguồn superseded không làm current evidence.
- [ ] Có baseline tái lập; G-04 đạt hoặc report ghi rõ thiếu hụt.
