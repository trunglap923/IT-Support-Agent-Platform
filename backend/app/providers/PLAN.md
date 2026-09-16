# Model và embedding adapters

Trạng thái: có text provider WP-01 và guarded fake/OpenAI embedding WP-04; generate tools còn theo WP-06.
Work packages: WP-01, WP-04, WP-06, WP-12, WP-13.
Nguồn: [kế hoạch tổng](../../../plan.md), mục 16; [thứ tự triển khai](../../../docs/implementation-roadmap.md).

## Mục tiêu

Cô lập giao tiếp OpenAI và cung cấp fake provider cho kiểm thử.

## Hợp đồng và trách nhiệm

- Generate trả tool calls hoặc typed final reply, usage và provider request ID.
- Embed trả vector cùng model/dimensions/usage; cấu hình model lấy từ mục 16, không hard-code trong graph.
- Ứng dụng tự quản lý context/queue; provider không quyết định quyền hay execute tools.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `base.py`
- `openai.py`
- `fake.py`
- `schemas.py`

## Phụ thuộc và phối hợp

- [backend/app/services/budget](../services/budget/PLAN.md)
- [backend/app/tools](../tools/PLAN.md)
- [backend/app/observability](../observability/PLAN.md)
- [backend/tests/contract](../../tests/contract/PLAN.md)

## Các bước triển khai

- [ ] PROV-01: Định nghĩa generate/embed contracts và fake responses theo scenario.
- [ ] PROV-02: Implement Responses/function-calling mapping theo cấu hình đã chốt; giữ tool call IDs.
- [ ] PROV-03: Đặt strict schema/output validation, token cap, timeout, store=false và retry một tầng.
- [ ] PROV-04: Nối budget reservation/finalization cho tất cả paid calls.
- [x] PROV-05: Tại WP-04 triển khai embed tối thiểu, dimension validation và budget guard; embedding cache còn theo WP-06.

## Điều kiện hoàn thành

- [x] Fake mode không cần secret/mạng và không bị tính là live evaluation.
- [x] Không phát sinh tool side effect trong provider adapter.
- [x] Live smoke/model-access M0 đạt với snapshot đã cấu hình; paid check vẫn chỉ chạy opt-in.
