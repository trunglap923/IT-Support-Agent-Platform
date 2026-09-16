# Xuất bản tài liệu và ACL

Trạng thái: upload/preview P50 và transactional publish/version/revoke/ACL lifecycle P51 đã triển khai.
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
- [x] DOC-02b: Provide explicit ingestion processing/status response; retry completed job idempotent.
- [x] DOC-03: Publish trong transaction khóa document, check expected version và switch current_version_id.
- [x] DOC-04a: Revoke/ACL changes tăng document access_version và optimistic version.
- [ ] DOC-04b: Thêm global corpus_revision nếu cần cache retrieval liên process.
- [x] DOC-05: Gate retrieval/history reads theo ACL mới nhất; history có nguồn mất quyền bị redaction.

## Điều kiện hoàn thành

- [x] Upload/parse thất bại không tạo draft hoặc file ngoài storage root.
- [x] Ingest thất bại không ảnh hưởng current source.
- [x] Publish wrong-document version hoặc stale version bị chặn.
- [x] Đổi ACL/revoke không lộ title/snippet/text trong retrieval hoặc lịch sử đã persist.
