# Manifest — metadata, ACL và snapshot dữ liệu

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-01, WP-04, WP-05, WP-13.
Nguồn: [kế hoạch tổng](../../plan.md), mục 6.3, 8, 13, 19; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Làm hợp đồng metadata cho seed, ingestion và evaluation thay vì rải thông tin trong tên file.

## Hợp đồng và trách nhiệm

- Mỗi tài liệu có document_key/version_label/title/authority/language/visibility/department_id/effective_at/expires_at/checksum/source provenance.
- visibility=department bắt buộc department_id; company/it_only phải department_id=null.
- Ground truth dùng document key + version + evidence span, không phụ thuộc chunk ids.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `documents.json`
- `corpus-snapshot.json`
- `seed-manifest.json`
- `schema.json`

## Phụ thuộc và phối hợp

- [data/knowledge](../knowledge/PLAN.md)
- [data/seed](../seed/PLAN.md)
- [evals/runner](../../evals/runner/PLAN.md)

## Các bước triển khai

- [ ] MANIFEST-01: Định nghĩa schema dựa đúng mục 6 kế hoạch tổng và validate các file dữ liệu.
- [ ] MANIFEST-02: Kiểm tra tham chiếu path/id, checksum, ngày hiệu lực và giới hạn scope.
- [ ] MANIFEST-03: Ghi snapshot corpus/chunker/preprocess version cho mỗi lần evaluation.
- [ ] MANIFEST-04: Lưu provenance/license nếu dùng tài liệu công khai; không đưa API key vào source URL.

## Điều kiện hoàn thành

- [ ] Manifest sai schema/ACL/path được phát hiện trước seed/ingestion.
- [ ] Có thể truy từ kết quả eval về đúng file/version đã dùng.
