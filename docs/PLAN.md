# Tài liệu — điều hướng và bàn giao dự án

Trạng thái: tài liệu bàn giao local đã hoàn thiện; video, independent review và remote CI còn mở.
Work packages: WP-01, WP-06, WP-14.
Nguồn: [kế hoạch tổng](../plan.md), mục 20, 21, 22; [thứ tự triển khai](implementation-roadmap.md).

## Mục tiêu

Giữ kế hoạch tổng, kế hoạch module, kiến trúc và hướng dẫn chạy thống nhất khi viết code.

## Hợp đồng và trách nhiệm

- plan.md là đặc tả tổng; PLAN.md từng module chuyển đặc tả thành checklist local.
- Roadmap WP-01..WP-14 quyết định thứ tự; cross-links module là quan hệ phối hợp, không phải DAG triển khai.
- Archive giữ bản gốc tham khảo, không dùng làm yêu cầu mới khi khác bản hiện hành.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `implementation-roadmap.md`
- `architecture.md`
- `demo-script.md`
- `adr/`
- `archive/plan-original.md`

## Phụ thuộc và phối hợp

- [docs/adr](adr/PLAN.md)
- [infra](../infra/PLAN.md)
- [reports](../reports/PLAN.md)

## Các bước triển khai

- [x] DOCS-01: Roadmap/mục lục và relative Markdown links có validator.
- [x] DOCS-02: ADR runtime/integration và architecture phản ánh ranh giới đã triển khai.
- [x] DOCS-03: README/commands/troubleshooting chỉ dùng lệnh đã kiểm chứng và ghi rõ giới hạn.
- [x] DOCS-04: Demo script trỏ tới RAG/tools/approval/memory/recovery automated evidence.
- [ ] DOCS-05: README/report/clean/restore đã có; video và independent reviewer còn thiếu nên release vẫn not ready.

## Điều kiện hoàn thành

- [x] Relative link checker chạy trên toàn bộ tracked Markdown; route/config/state chính được đối chiếu code.
- [x] README phân biệt implementation, local evidence, live/manual pending và production out-of-scope.
