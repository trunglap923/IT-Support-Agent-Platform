# Kiểm thử trình duyệt end-to-end

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-06, WP-09, WP-11, WP-12, WP-13.
Nguồn: [kế hoạch tổng](../../plan.md), mục 4, 19, 22; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Kiểm tra các hành trình người dùng và lỗi refresh/reconnect ở trình duyệt thật.

## Hợp đồng và trách nhiệm

- Suite mặc định chạy fake provider + seed test riêng, không cần paid API.
- Tách test contract/UI với live model evaluation; test fake không chứng minh chất lượng AI.
- Mỗi test cô lập user/session/data; không reset database demo đang dùng.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `playwright.config.ts`
- `fixtures.ts`
- `auth.spec.ts`
- `chat.spec.ts`
- `approval.spec.ts`
- `documents.spec.ts`
- `memory.spec.ts`

## Phụ thuộc và phối hợp

- [backend/tests/integration](../../backend/tests/integration/PLAN.md)
- [frontend/src/features](../src/features/PLAN.md)
- [data/seed](../../data/seed/PLAN.md)
- [.github/workflows](../../.github/workflows/PLAN.md)

## Các bước triển khai

- [ ] E2E-01: Dựng Playwright server/fixtures đăng nhập theo role.
- [ ] E2E-02: Kiểm thử chat/citation/refusal và reconnect, refresh trong waiting_approval.
- [ ] E2E-03: Kiểm thử approve hai lần, reject/expire, manual ticket form và IT update.
- [ ] E2E-04: Kiểm thử admin upload/publish/ACL và memory cross-conversation/consent/delete.
- [ ] E2E-05: Thu screenshot/trace khi thất bại, tránh token/cookie hoặc dữ liệu nhạy cảm trong artifact.

## Điều kiện hoàn thành

- [ ] Các luồng chính chạy lặp lại trong CI với dữ liệu cô lập.
- [ ] Negative cases URL đoán/sai role/citation revoke và duplicate submit đều pass.
