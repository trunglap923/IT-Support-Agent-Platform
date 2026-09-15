# Báo cáo — kết quả đo và bằng chứng portfolio

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-06, WP-13, WP-14.
Nguồn: [kế hoạch tổng](../plan.md), mục 19, 22; [thứ tự triển khai](../docs/implementation-roadmap.md).

## Mục tiêu

Lưu báo cáo kết quả thực tế, phân biệt rõ mục tiêu dự kiến với chỉ số đã đo.

## Hợp đồng và trách nhiệm

- Chưa có metric nào được coi là đạt chỉ vì scaffold hoặc fake suite chạy.
- Báo cáo versioned, có dataset/split/actor scope/environment/model/corpus và số lần chạy.
- Chỉ commit artifacts đã lọc dữ liệu nhạy cảm; log thô lớn giữ ở output bị gitignore.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `baseline.md`
- `evaluation-summary.md`
- `performance-cost.md`
- `release-checklist.md`
- `runs/<evaluation-id>/`

## Phụ thuộc và phối hợp

- [evals](../evals/PLAN.md)
- [backend/app/observability](../backend/app/observability/PLAN.md)
- [docs](../docs/PLAN.md)

## Các bước triển khai

- [ ] REPORT-01: Tạo baseline đầu tiên sau demo M2, ghi phương pháp và giới hạn.
- [ ] REPORT-02: Xuất tổng hợp G-01..G-10 kèm links tới artifacts an toàn và failure examples.
- [ ] REPORT-03: Báo cost thật/reserved-unknown, latency distribution và điều kiện load.
- [ ] REPORT-04: So sánh baseline/tools/memory không dùng task unsupported để nâng điểm giả.
- [ ] REPORT-05: Hoàn thiện release checklist với chưa đo/chưa đạt và quyết định phát hành.

## Điều kiện hoàn thành

- [ ] Mỗi con số trong README/video có nguồn báo cáo tái kiểm tra được.
- [ ] Báo cáo không chứa session, API key, private prompt hay dữ liệu doanh nghiệp thật.
