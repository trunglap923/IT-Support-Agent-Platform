# Prompt và output schema

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-06, WP-12, WP-13.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 8.3, 9, 12, 16; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Version hóa hướng dẫn agent và memory để có thể đánh giá thay đổi.

## Hợp đồng và trách nhiệm

- Prompt coi tài liệu/tool/memory là evidence, không nguồn cấp quyền.
- Model output là proposal; final receipt của ticket thuộc application template.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `agent.md`
- `memory_extraction.md`
- `reply.schema.json`
- `prompt_manifest.json`

## Phụ thuộc và phối hợp

- [backend/app/agent](../agent/PLAN.md)
- [backend/app/tools](../tools/PLAN.md)
- [backend/app/memory](../memory/PLAN.md)
- [evals/cases](../../../evals/cases/PLAN.md)

## Các bước triển khai

- [ ] PROMPT-01: Viết agent prompt cho ba domain và logic hỏi thêm/escalation có căn cứ.
- [ ] PROMPT-02: Định nghĩa answer schema/citation IDs và tool-use rules khớp executor.
- [ ] PROMPT-03: Viết memory extraction prompt chỉ user fact allowlist, theo thiết bị.
- [ ] PROMPT-04: Gắn prompt/schema version vào run và evaluation artifacts.
- [ ] PROMPT-05: Review bằng development cases; không tune trực tiếp bằng holdout.

## Điều kiện hoàn thành

- [ ] Không lấy proposed step làm confirmed attempted step.
- [ ] Không dùng public reference để bịa corporate policy hoặc hostname.
- [ ] Prompt change có paired evaluation và không thay permission enforcement.
