# Logs, trace và feedback telemetry

Trạng thái: Langfuse trace, usage metadata và owner-scoped message feedback đã có.
Work packages: WP-03, WP-04, WP-06, WP-13.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 18; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Liên kết request/run/tool/usage để debug và làm bằng chứng portfolio.

## Hợp đồng và trách nhiệm

- Langfuse Cloud là trace sink; DB audit phục vụ business actions.
- LOG_PROMPTS=false; metadata-only mặc định; raw I/O chỉ được capture qua redaction khi bật rõ ràng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `logging.py`
- `tracing.py`
- `redaction.py`
- `metrics.py`

## Phụ thuộc và phối hợp

- [backend/app/services/budget](../services/budget/PLAN.md)
- [backend/app/jobs](../jobs/PLAN.md)
- [reports](../../../reports/PLAN.md)
- [backend/tests/unit](../../tests/unit/PLAN.md)

## Các bước triển khai

- [x] OBS-01a: Gắn run ID và pseudonymous actor; request/conversation propagation còn WP-13.
- [ ] OBS-02: Instrument queue wait, retrieval, model, MCP, approval wait, validation, memory.
- [x] OBS-03: Thu token/cost từ provider response và ledger cho embedding/chat.
- [x] OBS-04a: Gắn feedback metadata; API/UI lưu feedback có ownership, CSRF và idempotent update.
- [ ] OBS-05: Thêm redaction tests trên mọi sink và document dashboard/report queries.

## Điều kiện hoàn thành

- [ ] Một run truy được toàn bộ các bước qua trace ID mà không cần hidden reasoning.
- [ ] Langfuse outage không làm fail chat/ticket.
- [ ] Approval wait được tách khỏi active latency; unknown cost không báo 0.
