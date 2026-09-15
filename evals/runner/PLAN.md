# Evaluation runner — chạy, chấm và lưu bằng chứng

Trạng thái: có validator offline M0; chưa có execution/scoring runner.
Work packages: WP-05, WP-06, WP-13.
Nguồn: [kế hoạch tổng](../../plan.md), mục 16, 19, 20.4; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Tự động chạy case trên môi trường cô lập, thu trace/DB effects và xuất báo cáo đối chiếu được.

## Hợp đồng và trách nhiệm

- Reuse provider/services của backend; không viết một agent khác chỉ dành cho eval.
- Fake runs kiểm tra harness; live mode yêu cầu cấu hình explicit, có reservation budget dùng chung.
- Ghi run ids, model snapshot, prompt/rubric version, commit hoặc uncommitted marker, corpus checksum, seed, concurrency, cost/latency.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `cli.py`
- `load_cases.py`
- `harness.py`
- `scorers.py`
- `metrics.py`
- `report.py`

## Phụ thuộc và phối hợp

- [backend/app/providers](../../backend/app/providers/PLAN.md)
- [backend/app/services/budget](../../backend/app/services/budget/PLAN.md)
- [backend/app/observability](../../backend/app/observability/PLAN.md)
- [evals/cases](../cases/PLAN.md)
- [evals/rubrics](../rubrics/PLAN.md)
- [reports](../../reports/PLAN.md)

## Các bước triển khai

- [ ] RUNNER-01: Tạo CLI chọn split/configuration/repetitions/output và validate trước khi chạy.
- [ ] RUNNER-02: Thiết lập test DB/storage độc lập, cấm reset target không xác định là test.
- [ ] RUNNER-03: Chạy scripted conversation/approval/failure và đọc thay đổi DB để chấm side effects.
- [ ] RUNNER-04: Thêm scorer deterministic, semantic review export và aggregation không bỏ silent failures.
- [ ] RUNNER-05: Giới hạn API spend/concurrency, checkpoint tiến độ eval để có thể tiếp tục có kiểm soát.

## Điều kiện hoàn thành

- [ ] Chạy lại cùng fake seed cho kết quả nhất quán; live kết quả giữ cả lần lỗi và biến động.
- [ ] Báo cáo ba cấu hình trên đúng nhóm task có thể so sánh.
- [ ] Artifacts không chứa secret/raw checkpoint; live eval không tự chạy trong PR CI.
