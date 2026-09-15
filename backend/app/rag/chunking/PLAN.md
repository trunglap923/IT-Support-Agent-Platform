# Chia đoạn tài liệu

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-04, WP-05.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 8.1, 19.2; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Tạo chunk đủ ngữ cảnh, giữ được lệnh và evidence span.

## Hợp đồng và trách nhiệm

- Đầu vào: parsed blocks kèm page/heading; đầu ra: ordered chunks với source spans.
- Mục tiêu 400–600 token, hard cap 800, overlap tối đa 80.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `splitter.py`
- `normalization.py`
- `metadata.py`

## Phụ thuộc và phối hợp

- [data/knowledge](../../../../data/knowledge/PLAN.md)
- [backend/tests/unit](../../../tests/unit/PLAN.md)
- [evals/cases](../../../../evals/cases/PLAN.md)

## Các bước triển khai

- [ ] CHUNK-01: Chuẩn hóa whitespace/header/footer mà không đổi nội dung command/error code.
- [ ] CHUNK-02: Ưu tiên heading/paragraph; giữ code block cùng hướng dẫn liên quan.
- [ ] CHUNK-03: Block quá dài được chia có continuation metadata, không cắt lệnh lặng lẽ.
- [ ] CHUNK-04: Sinh ordinal, token_count, content_hash và chunker_version.
- [ ] CHUNK-05: Map evidence span của eval sang chunks để không khóa ground truth theo chunk IDs.

## Điều kiện hoàn thành

- [ ] Output xác định với cùng text/config; ordinal không trùng trong version.
- [ ] Không chunk vượt hard cap; metadata page/section truy vết được.
- [ ] Test trên tiếng Việt/Anh, command nhiều dòng và tài liệu nhiều heading.
