# LangGraph runtime

Trạng thái: spike checkpoint/recovery M0 đã đạt; graph nghiệp vụ vẫn chưa triển khai.
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

- [ ] AG-01: Định nghĩa state serializable, schema_version và status/outcome tách biệt.
- [ ] AG-02: Xây graph load → decision → read tool/final reply, dùng context builder.
- [ ] AG-03: Thêm propose idempotent → interrupt → recheck → write → receipt nodes.
- [ ] AG-04: Áp dụng tối đa 4 model calls kể cả retry/repair, 4 read calls, 1 approved write/run, recursion=24 và active deadline 60 giây mỗi execution segment.
- [ ] AG-05: Nối PostgreSQL checkpointer, run locking, replay receipt và memory job sau khi final persist.

## Điều kiện hoàn thành

- [ ] UC-01/02/03/04/09 hoạt động đúng và graph kết thúc khi hết budget.
- [ ] Restart/resume dùng đúng checkpoint; không có write trước interrupt.
- [ ] Graph replay không tạo thêm ticket và không dùng quyền từ state cũ.

## Bằng chứng spike M0

- `checkpoint_spike.py` chạy pause và resume trong hai Python process khác nhau, dùng cùng
  `thread_id=run_id` và PostgreSQL checkpointer thật.
- Integration test chỉ chạy khi có `CHECKPOINT_DATABASE_URL`; CI mặc định skip và không
  tự kết nối database bên ngoài.
- Spike chỉ chứng minh checkpoint recovery. Receipt/idempotency, approval business record,
  run locking và authorization recheck vẫn thuộc WP-08/WP-10.
