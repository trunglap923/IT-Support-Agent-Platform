# Tài liệu — điều hướng và bàn giao dự án

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
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

- [ ] DOCS-01: Duy trì mục lục mọi PLAN.md và liên kết WP tới module cần sửa.
- [ ] DOCS-02: Ghi ADR khi đổi thiết kế nền tảng; cập nhật đồng thời kế hoạch tổng và module liên quan.
- [ ] DOCS-03: Viết hướng dẫn setup từ lệnh đã chạy kiểm chứng; đánh dấu rõ lệnh còn dự kiến.
- [ ] DOCS-04: Chuẩn bị kịch bản demo có bằng chứng cho RAG/tools/approval/memory/recovery.
- [ ] DOCS-05: Bàn giao README, video, báo cáo và clean-machine/restore checklist khi V1 đạt gate.

## Điều kiện hoàn thành

- [ ] Không có link nội bộ hỏng; tên route/config/state đồng nhất giữa tài liệu.
- [ ] Người mới biết bắt đầu WP nào và phân biệt phần đã làm với phần dự kiến.
