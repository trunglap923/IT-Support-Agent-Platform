# RAG và knowledge lifecycle

Trạng thái: ingestion/chunk storage M2 đã triển khai; retrieval/citations theo WP-05.
Work packages: WP-04, WP-05, WP-11.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 6, 8; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp kiến thức có nguồn, có phiên bản và đúng quyền cho agent.

## Hợp đồng và trách nhiệm

- Input: tài liệu admin duyệt hoặc query cùng principal.
- Output: draft version hoặc evidence có source_id/version/page/section.
- Current version chỉ đổi qua document service; ingestion không tự publish.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `ingestion/`
- `chunking/`
- `retrieval/`
- `citations/`

## Phụ thuộc và phối hợp

- [backend/app/rag/ingestion](ingestion/PLAN.md)
- [backend/app/rag/chunking](chunking/PLAN.md)
- [backend/app/rag/retrieval](retrieval/PLAN.md)
- [backend/app/rag/citations](citations/PLAN.md)
- [backend/app/services/documents](../services/documents/PLAN.md)

## Các bước triển khai

- [x] RAG-01: Hoàn thành ingestion và chunking với dữ liệu do dự án sở hữu.
- [x] RAG-02: Tạo embedding space thống nhất và scoped hybrid retrieval.
- [x] RAG-03: Bổ sung citation DTO/validation và xử lý câu hỏi thiếu căn cứ; source endpoint nối ở WP-06.
- [ ] RAG-04: Nối admin preview/publish/archive; đo retrieval baseline trước reranker.

## Điều kiện hoàn thành

- [ ] UC-01/07/08 chạy với corpus seed và dữ liệu trái quyền.
- [ ] Bản cũ vẫn hoạt động khi ingest bản mới lỗi.
- [ ] Có evidence labels ổn định để so sánh chunker/retriever.
