# LangGraph runtime

Trạng thái: bounded RAG graph WP-06 và approval interrupt/checkpoint/receipt recovery WP-08–WP-10 đã có.
Work packages: WP-06, WP-08, WP-10, WP-12.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 9, 11, 12; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Điều phối một agent có tools, checkpoint và approval bền vững.

## Hợp đồng và trách nhiệm

- thread_id=run_id do backend sinh; conversation history nằm ở application DB.
- Run kind chat đi qua model; manual_ticket đi thẳng draft/approval.
- Model chỉ đề xuất action; ticket write do executor sau xác nhận.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `state.py`
- `graph.py`
- `nodes.py`
- `checkpoint.py`
- `runner.py`

## Phụ thuộc và phối hợp

- [backend/app/agent/context](context/PLAN.md)
- [backend/app/tools](../tools/PLAN.md)
- [backend/app/providers](../providers/PLAN.md)
- [backend/app/services/approvals](../services/approvals/PLAN.md)
- [backend/app/jobs](../jobs/PLAN.md)

## Các bước triển khai

- [x] AG-01: Định nghĩa state serializable, schema_version và status/outcome tách biệt.
- [x] AG-02a: Xây RAG graph load → retrieve → evidence decision → final reply, dùng context builder.
- [x] AG-02b: Route service/ticket read tools từ support graph theo model decision.
- [x] AG-03: Thêm approval graph interrupt → recheck actor/hash → write → receipt.
- [x] AG-04: Áp dụng tối đa 4 model calls, 4 retrieval calls và recursion=24; write/deadline nối ở WP-08.
- [x] AG-05a: Nối PostgreSQL checkpointer, run locking và replay receipt.
- [x] AG-05b: Enqueue memory extraction sau khi final persist ở WP-12.

## Điều kiện hoàn thành

- [ ] UC-01/02/03/04/09 hoạt động đúng và graph kết thúc khi hết budget.
- [x] Restart/resume dùng đúng checkpoint; không có write trước interrupt.
- [x] Graph replay không tạo thêm ticket và actor/hash được đối chiếu lại từ database.

## Bằng chứng spike M0

- `checkpoint_spike.py` chạy pause và resume trong hai Python process khác nhau, dùng cùng
  `thread_id=run_id` và PostgreSQL checkpointer thật.
- Integration test chỉ chạy khi có `CHECKPOINT_DATABASE_URL`; CI mặc định skip và không
  tự kết nối database bên ngoài.
- Spike chỉ chứng minh checkpoint recovery. Receipt/idempotency, approval business record,
  run locking và authorization recheck vẫn thuộc WP-08/WP-10.
