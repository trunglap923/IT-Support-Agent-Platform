# Chiến lược kiểm thử backend

Trạng thái: unit/contract foundation cùng PostgreSQL/Redis integration WP-03 đã có; fixtures/failure suites mở rộng theo feature.
Work packages: WP-01, WP-02, WP-03, WP-13.
Nguồn: [kế hoạch tổng](../../plan.md), mục 19; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Kiểm tra deterministic correctness bằng fake AI và database/broker thật khi cần.

## Hợp đồng và trách nhiệm

- Unit/integration/contract mặc định không gọi paid API.
- Test DB/Redis namespace riêng; không reset database đang dùng cho demo.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `conftest.py`
- `factories.py`
- `unit/`
- `integration/`
- `contract/`

## Phụ thuộc và phối hợp

- [backend/tests/unit](unit/PLAN.md)
- [backend/tests/integration](integration/PLAN.md)
- [backend/tests/contract](contract/PLAN.md)
- [evals](../../evals/PLAN.md)

## Các bước triển khai

- [x] TEST-01a: Tạo database tạm, identity/session và actor/department fixtures WP-02.
- [ ] TEST-01b: Thêm device, clock và fault injection khi feature tiêu thụ tồn tại.
- [x] TEST-02: Chia unit, integration và cross-boundary contract suites.
- [ ] TEST-03: Gắn regression cases vào các gates G-01/G-02/G-03/G-08.
- [x] TEST-04a: Cung cấp command WP-02 bắt buộc PostgreSQL và không pass giả do skip.
- [x] TEST-04b: Tách command WP-03 bắt buộc PostgreSQL/Redis thật và cleanup namespace test.
- [ ] TEST-04c: Phân suite/giữ artifacts đã redact khi có E2E/eval reports.

## Điều kiện hoàn thành

- [ ] Tests kiểm tra hành vi và race conditions, không chỉ so khớp implementation.
- [ ] Có thể chạy fake-mode hoàn toàn không có API keys.
- [ ] Live quality được báo cáo bởi evals, không trộn với unit pass rate.
