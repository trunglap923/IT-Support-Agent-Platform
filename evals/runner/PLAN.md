# Evaluation runner — chạy, chấm và lưu bằng chứng

Trạng thái: runner deterministic và live opt-in đã có; live semantic evaluation chưa được chạy.
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

- [x] RUNNER-01: Tạo CLI chọn split/configuration/repetitions/output và validate trước khi chạy.
- [x] RUNNER-02: Thiết lập database tạm prefix `test_retrieval_eval_` và guard trước cleanup.
- [ ] RUNNER-03: LangGraph RAG và scripted contract đã có; actual scoped DB-effect measurement còn ở P58.
- [x] RUNNER-04: Thêm scorer deterministic retrieval/no-answer/scope có mẫu số; semantic review còn WP-06.
- [x] RUNNER-05: Live mode opt-in, giới hạn call/output/cost; resume/checkpoint batch chưa cần cho quota nhỏ.

## Điều kiện hoàn thành

- [x] Chạy lại cùng fake seed cho kết quả nhất quán; live artifact giữ từng lần chạy.
- [ ] Báo cáo ba cấu hình trên đúng nhóm task có thể so sánh.
- [x] Artifacts không chứa secret/raw checkpoint; live eval không tự chạy trong PR CI.
