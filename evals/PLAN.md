# Evaluation — đo chất lượng và điều kiện release

Trạng thái: schema và 30 case M0 đã có; chưa có live runner/baseline.
Work packages: WP-01, WP-05, WP-06, WP-13.
Nguồn: [kế hoạch tổng](../plan.md), mục 19, 21, 22; [thứ tự triển khai](../docs/implementation-roadmap.md).

## Mục tiêu

Chứng minh chất lượng bằng bộ ca có đáp án và tác động DB, tách với test chức năng dùng fake provider.

## Hợp đồng và trách nhiệm

- M0 viết 30 ca đầu; M6 đủ 120 ca, 80 development + 40 holdout, group-aware split.
- So sánh RAG baseline; agent + tools; agent + tools + memory trên cùng điều kiện thích hợp.
- Live evaluation có quota guard và opt-in; security/tool effects chấm bằng code, câu trả lời cần rubric/human review.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `cases/`
- `rubrics/`
- `runner/`

## Phụ thuộc và phối hợp

- [evals/cases](cases/PLAN.md)
- [evals/rubrics](rubrics/PLAN.md)
- [evals/runner](runner/PLAN.md)
- [reports](../reports/PLAN.md)

## Các bước triển khai

- [x] EVAL-01: Chốt case schema, nhóm tình huống và evidence ground truth trước tinh chỉnh prompt.
- [ ] EVAL-02: Xây baseline retrieval/no-answer từ M2, lưu cả thất bại.
- [ ] EVAL-03: Nối runner tới các cấu hình ứng dụng và kiểm tra DB effects có scope.
- [ ] EVAL-04: Chạy live agent cases ít nhất ba lần, báo số mẫu/biến động/cost.
- [ ] EVAL-05: Tổng hợp G-01..G-10; ghi rõ gate chưa đo hoặc chưa đạt, không coi fake run là AI quality.

## Điều kiện hoàn thành

- [ ] 120 ca đúng split/nhóm, kết quả có model/prompt/corpus version.
- [ ] Release gates được báo cả mẫu số, phương pháp và giới hạn; không thay ngưỡng để hợp kết quả.
