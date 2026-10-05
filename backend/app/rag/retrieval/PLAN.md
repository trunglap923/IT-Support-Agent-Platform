# Tìm kiếm hybrid có phân quyền

Trạng thái: hybrid RRF, rerank đặc trưng, mở rộng chunk lân cận có ACL và ngân sách citation đã triển khai.
Work packages: WP-05, WP-13.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 8.2, 19; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Tìm evidence bằng vector và lexical search trong tập tài liệu user được đọc.

## Hợp đồng và trách nhiệm

- Input query + server principal; model không truyền SQL/ACL filters.
- Cosine exact top 20 + PostgreSQL FTS `ts_rank_cd` top 20 → RRF(k=60) → top 5.
- Sparse branch luôn dùng raw query; alias expansion chỉ áp dụng cho dense semantic query.
- PostgreSQL FTS là sparse baseline hiện tại, chưa được gọi là BM25.
- Reranker/HNSW tắt ban đầu; model space theo mục 16 của kế hoạch tổng.
- Retrieval reranker hiện là weighted feature baseline: term coverage, exact identifier, RRF và dense score.
- Parent/neighbor expansion chỉ thêm leaf chunks trong cùng current-version/ACL scope; citation vẫn định danh chunk nguồn cụ thể.
- Evidence selection mặc định tối đa 5 citations và 6.000 estimated input tokens; nội dung citation được cắt theo ngân sách. Chỉ khử nội dung gần trùng trong cùng document-version để không loại nguồn độc lập.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `query.py`
- `filters.py`
- `analysis.py`
- `dense.py`
- `sparse.py`
- `fusion.py`
- `store.py`

## Phụ thuộc và phối hợp

- [backend/app/auth](../../auth/PLAN.md)
- [backend/app/repositories](../../repositories/PLAN.md)
- [backend/app/providers](../../providers/PLAN.md)
- [backend/app/rag/citations](../citations/PLAN.md)
- [evals/runner](../../../../evals/runner/PLAN.md)

## Các bước triển khai

- [x] RET-01: Tạo predicate visibility/department/current version/archive/effective/expiry dùng chung hai nhánh search.
- [x] RET-02: Xây query embedding và PostgreSQL full-text query.
- [x] RET-02a: Mở rộng alias Việt-Anh có giới hạn cho VPN/Docker/GitLab trong fake/demo mode.
- [x] RET-03: Fuse ranks bằng RRF thay vì cộng score khác thang đo.
- [x] RET-04: Đo Recall@5 trên cases answerable, tách no-answer cases.
- [x] RET-05: Retrieval artifact lưu corpus manifest hash, parser/chunker/embedding và threshold versions.
- [x] RET-06: Tách interface query analyzer, dense, sparse và fusion khỏi orchestration.
- [x] RET-07: Raw sparse query giữ exact identifier; RRF là thứ tự xếp hạng chính.
- [x] RET-08: Trace số candidate và latency riêng cho embedding/dense/sparse/fusion.
- [x] RET-09: Tạo candidate pool bounded, rerank bằng score query-aware sau hybrid fusion.
- [x] RET-10: Bổ sung neighboring và parent-section leaf expansion có chung ACL/current-version predicate.
- [x] RET-11: Giới hạn context evidence theo estimated token budget, khử chunk trùng và chọn tối đa 5 citation.
- [x] RET-12: Chuẩn hóa query-analysis contract gồm intent, confidence, exact terms, service/product/OS/error/version và metadata filters.
- [x] RET-13: Chạy deterministic extraction trước; model analyzer chỉ được gọi một lần khi confidence thấp và có usage budget.
- [x] RET-14: Multi-query fallback chỉ chạy theo policy confidence, tối đa hai semantic queries và luôn giữ raw sparse query/exact tokens.
- [x] RET-15: Request policy ánh xạ structured intent sang tool; knowledge tool khóa retrieval vào current user request.
- [x] RET-16: Resolve low-confidence intent trước runtime và dùng chung một QuerySpec cho policy, LangGraph, OpenAI Agents và retrieval.
- [x] RET-17: Mở rộng Phase 5.0 evaluation lên 42 cases với nhãn section/required terms và metrics chunk/citation.

## Điều kiện hoàn thành

- [x] Không trả title/snippet/chunk trái quyền tới context, logs hoặc UI.
- [x] FTS và vector cùng scope; nguồn superseded không làm current evidence.
- [x] Có baseline tái lập; G-04 đạt và report ghi rõ giới hạn fake embedding.
- [x] Ghi benchmark Phase 3 đối chiếu với Phase 2 trong `reports/phase3/retrieval-benchmark.md`.
- [x] Ghi benchmark Phase 4 và regression tests cho model-call limit, fallback, exact-token preservation và current-query isolation.
- [ ] Chạy ablation cùng corpus cho Phase 2 RRF-only, reranker-only và full expansion; chỉ chốt trọng số sau khi ranking/citation đạt baseline.

Bằng chứng: `test_hybrid_retrieval.py`, `test_demo_document_seed.py`,
`test_openai_agents_runtime.py`, `test_retrieval_orchestration.py` và
`reports/phase4/query-intelligence-benchmark.md`.
