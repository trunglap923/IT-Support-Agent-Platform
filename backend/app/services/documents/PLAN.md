# Xuất bản tài liệu và ACL

Trạng thái: upload PDF an toàn và admin draft preview P50 đã triển khai; publication lifecycle thuộc P51.
Work packages: WP-04, WP-05, WP-11.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 6, 8, 13, 14; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Quản lý document/version, quyền đọc và thời điểm version trở thành current.

## Hợp đồng và trách nhiệm

- Document là identity; version là publication; chunk luôn thuộc một version.
- Publish chỉ ready version đã đến effective_at; visibility department cần department_id.
- Một current version/document; ingestion không tự thay nguồn đang phục vụ.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `service.py`
- `publishing.py`
- `access.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [backend/app/auth](../../auth/PLAN.md)
- [backend/app/rag/ingestion](../../rag/ingestion/PLAN.md)
- [backend/app/repositories](../../repositories/PLAN.md)
- [backend/app/rag/citations](../../rag/citations/PLAN.md)
- [frontend/src/features/documents](../../../../frontend/src/features/documents/PLAN.md)

## Các bước triển khai

- [x] DOC-01: Create document/version/job từ admin upload và metadata đã validate.
- [x] DOC-02a: Provide bounded PDF draft preview endpoint qua service method.
- [ ] DOC-02b: Provide ingestion status/retry endpoint ở P51.
- [ ] DOC-03: Publish trong transaction khóa document, check expected version và switch current_version_id.
- [ ] DOC-04: Archive/ACL changes tăng access_version và corpus_revision.
- [ ] DOC-05: Gate source/download/history reads theo ACL mới nhất; phối hợp cleanup để giữ provenance.

## Điều kiện hoàn thành

- [x] Upload/parse thất bại không tạo draft hoặc file ngoài storage root.
- [ ] Ingest thất bại không ảnh hưởng current source.
- [ ] Publish wrong-document version hoặc stale version bị chặn.
- [ ] Đổi ACL giữa retrieve/final/download không lộ title/snippet/text trái quyền.
