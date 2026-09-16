# Nhập và trích xuất tài liệu

Trạng thái: PDF text parser có giới hạn và error codes đã triển khai; pipeline ở bước tiếp theo.
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
- [ ] ING-02: Lưu bằng server-generated storage key trong volume riêng.
- [ ] ING-03: Parse trong subprocess có timeout/resource limits, giữ page numbering từ 1.
- [ ] ING-04: Gọi chunking và embedding theo batch, lưu progress vào DB.
- [ ] ING-05: Dedupe theo document/version/checksum/config, đánh dấu ready chỉ khi tất cả chunks hợp lệ.

## Điều kiện hoàn thành

- [ ] PDF text giữ đúng page; Markdown giữ heading và page=null.
- [ ] PDF scan/file lỗi trả failed với lý do, không đổi current_version_id.
- [ ] Retry không tạo duplicate chunks; không log raw file/secret.
