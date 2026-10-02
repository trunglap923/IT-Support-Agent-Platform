# Nhập và trích xuất tài liệu

Trạng thái: PDF/Markdown parser có giới hạn và pipeline structure → section → chunk → embed → store đã triển khai.
Work packages: WP-04, WP-11.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 6, 8.1; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Biến PDF text/Markdown thành draft version có text và provenance.

## Hợp đồng và trách nhiệm

- File tối đa 10 MB/100 trang; extracted text tối đa 1 MB.
- Chỉ upload file local; scan/encrypted PDF không hỗ trợ ở V1.
- Đầu ra giữ document/version, page/heading, checksum và parser_version.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `pipeline.py`
- `pdf_parser.py`
- `markdown_parser.py`
- `storage.py`

## Phụ thuộc và phối hợp

- [backend/app/rag/chunking](../chunking/PLAN.md)
- [backend/app/providers](../../providers/PLAN.md)
- [backend/app/jobs](../../jobs/PLAN.md)
- [backend/app/services/documents](../../services/documents/PLAN.md)
- [data/manifests](../../../../data/manifests/PLAN.md)

## Các bước triển khai

- [x] ING-01: Kiểm tra PDF signature/size/page/text limits trước ingestion.
- [x] ING-02: Lưu bằng server-generated storage key trong volume riêng.
- [x] ING-03: Parse trong subprocess có timeout/resource limits, giữ page numbering từ 1.
- [x] ING-04: Gọi chunking và embedding theo batch, lưu progress vào DB.
- [x] ING-05: Dedupe theo job identity và deterministic chunks; chỉ đánh dấu ready khi lưu đủ chunks.
- [x] ING-06: Re-index có dry-run, giới hạn seed corpus và paid-provider budget guard.
- [x] ING-07: Markdown giữ heading hierarchy/content types; PDF tạo section theo page.
- [x] ING-08: Lưu parent section riêng và nối leaf chunks bằng section_id/path.

## Điều kiện hoàn thành

- [x] PDF text giữ đúng page; Markdown giữ heading và page=null.
- [x] PDF scan/file lỗi trả failed với lý do, không đổi current_version_id.
- [x] Retry không tạo duplicate chunks; không log raw file/secret.
- [x] Dữ liệu cũ được backfill thành section phẳng; re-ingest nâng cấp lên hierarchy đầy đủ.
