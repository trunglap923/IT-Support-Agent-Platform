# Evaluation rubrics — cách chấm và release gates

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-01, WP-05, WP-13.
Nguồn: [kế hoạch tổng](../../plan.md), mục 19.3, 19.5; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Giữ cách chấm nhất quán, giải thích được và không thay sau khi xem kết quả holdout.

## Hợp đồng và trách nhiệm

- G-01..G-10 và ngưỡng lấy nguyên từ mục 19.3 kế hoạch tổng.
- Citation validity và mức hỗ trợ ngữ nghĩa là hai metric khác nhau.
- LLM-as-judge không quyết định quyền, số ticket hoặc tác động DB; no-answer không tính vào mẫu số Recall@5.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `retrieval.md`
- `answers.md`
- `task-success.md`
- `memory.md`
- `release-gates.md`

## Phụ thuộc và phối hợp

- [evals/cases](../cases/PLAN.md)
- [evals/runner](../runner/PLAN.md)
- [reports](../../reports/PLAN.md)

## Các bước triển khai

- [ ] RUBRIC-01: Định nghĩa công thức/mẫu số cho Recall@5, citation validity/support, abstention, task/memory success.
- [ ] RUBRIC-02: Viết ví dụ pass/fail cho claim thiếu bằng chứng và tool arguments sai.
- [ ] RUBRIC-03: Chốt cách đo latency với ba lượt đồng thời, tách approval wait và báo lỗi/cost.
- [ ] RUBRIC-04: Thiết lập human review có checklist và ghi disagreement với auto-judge.
- [ ] RUBRIC-05: Version rubric, áp dụng cùng phiên bản cho cấu hình được so sánh.

## Điều kiện hoàn thành

- [ ] Người khác có thể tái chấm một sample và giải thích cùng tiêu chí.
- [ ] Không báo 100% khi nhóm ca chưa chạy; security=0 chỉ áp dụng phạm vi suite đã đo.
