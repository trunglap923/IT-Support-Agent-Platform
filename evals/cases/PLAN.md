# Evaluation cases — dữ liệu kiểm thử có đáp án

Trạng thái: 120 case với split 80/40 đã hoàn thành.
Work packages: WP-01, WP-05, WP-06, WP-12, WP-13.
Nguồn: [kế hoạch tổng](../../plan.md), mục 19.2, 19.4; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Tạo 120 kịch bản có actor, dữ liệu ban đầu, bằng chứng và kết quả mong đợi cụ thể.

## Hợp đồng và trách nhiệm

- Phân bố cân bằng: mỗi nhóm RAG, permission, tool, approval, memory, failure có 20 ca.
- Case có case_id/split/scenario_group/actor/state/script/evidence/required facts/forbidden actions/DB effects/rubric version.
- Paraphrase cùng incident/document task ở cùng split; holdout không dùng để tuning.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `development.jsonl`
- `holdout.jsonl`
- `schema.json`
- `split-manifest.json`

## Phụ thuộc và phối hợp

- [data/seed](../../data/seed/PLAN.md)
- [data/manifests](../../data/manifests/PLAN.md)
- [evals/rubrics](../rubrics/PLAN.md)

## Các bước triển khai

- [x] CASES-01: Viết 30 ca M0 gồm happy path, no-answer, sai quyền, approval và memory consent.
- [x] CASES-02: Gắn evidence bằng stable document key/version/section/span, không fixed chunk id.
- [x] CASES-03: Tạo scripted interactions cho approve/reject/expire và hai conversation cùng/khác thiết bị.
- [x] CASES-04: Bổ sung fault injection Redis timeout, worker crash, usage unknown và ACL/owner denial.
- [x] CASES-05: Validate đủ 120 ca, giữ 80/40 theo scenario_group; holdout có manifest/checksum riêng.

## Điều kiện hoàn thành

- [x] Không trùng case_id hoặc rò scenario_group giữa split.
- [x] Mỗi expected DB write có actor/approval/idempotency rõ; ca no-answer được chấm riêng retrieval recall.
