# Chia đoạn tài liệu

Trạng thái: deterministic semantic/window chunker M2 đã triển khai.
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

- [x] CHUNK-01: Chuẩn hóa whitespace xác định và giữ nguyên token/error code.
- [x] CHUNK-02: Ưu tiên heading/paragraph; code block trong hard cap được giữ cùng hướng dẫn liền trước.
- [x] CHUNK-03: Block quá dài được chia theo cửa sổ có source token span và overlap.
- [x] CHUNK-04: Sinh ordinal, token_count, content_hash và chunker_version.
- [x] CHUNK-05: Eval dùng document/version/section/span và validator đối chiếu span với corpus snapshot, không khóa chunk ID.

## Điều kiện hoàn thành

- [x] Output xác định với cùng text/config; ordinal không trùng trong version.
- [x] Không chunk vượt hard cap; metadata page/section truy vết được.
- [x] Test trên tiếng Việt/Anh, command nhiều dòng và tài liệu nhiều heading.
