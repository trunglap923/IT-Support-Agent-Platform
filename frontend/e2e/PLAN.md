# Kiểm thử trình duyệt end-to-end

Trạng thái: Playwright bao phủ ticket/operations, document admin và memory lifecycle local.
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

- [x] E2E-01: Dựng Playwright server và session mocks theo role.
- [ ] E2E-02: Kiểm thử chat/citation/refusal và reconnect, refresh trong waiting_approval.
- [x] E2E-03a: Kiểm thử approve/reject, manual ticket form và IT resolve/reopen.
- [ ] E2E-03b: Bổ sung browser race cho approve hai lần và expiry.
- [x] E2E-04a: Kiểm thử admin upload/preview/process/publish/revoke và employee UI denial.
- [x] E2E-04b: Kiểm thử UI consent/device/confirm/edit/delete; backend kiểm tra cross-conversation/epoch.
- [x] E2E-05: Thu screenshot/trace khi thất bại; suite dùng identity/token giả không nhạy cảm.

## Điều kiện hoàn thành

- [ ] Các luồng chính chạy lặp lại trong CI với dữ liệu cô lập (CI remote đang tạm hoãn).
- [x] Sai role cho operations/service update bị chặn trong browser/API regression.
- [ ] Bổ sung URL đoán, citation revoke và duplicate browser submit ở các WP liên quan.
