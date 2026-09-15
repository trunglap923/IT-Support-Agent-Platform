# UI — chat, nguồn tham khảo và approval

Trạng thái: run status/SSE monitor WP-03 đã có; chat message/citation/approval thuộc WP-06/WP-09.
Work packages: WP-06, WP-09, WP-12.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 4, 7, 9, 11, 12, 14; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Cung cấp luồng chính từ câu hỏi tới câu trả lời có nguồn hoặc ticket đã xác nhận.

## Hợp đồng và trách nhiệm

- WP-06 chỉ cần lịch sử, gửi câu hỏi, trạng thái run và citation; WP-09 thêm tools/approval.
- Một conversation có tối đa một run chưa kết thúc, gồm waiting_approval.
- Không fake token streaming; chỉ render final response đã backend kiểm tra.
- Nút xác nhận/reject mang approval id/version; không gửi graph state hoặc sửa canonical arguments.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `ChatPage.tsx`
- `ConversationList.tsx`
- `MessageList.tsx`
- `Composer.tsx`
- `RunStatus.tsx`
- `CitationPanel.tsx`
- `ApprovalCard.tsx`

## Phụ thuộc và phối hợp

- [frontend/src/api](../../api/PLAN.md)
- [frontend/src/components](../../components/PLAN.md)
- [backend/app/agent](../../../../backend/app/agent/PLAN.md)
- [backend/app/services/approvals](../../../../backend/app/services/approvals/PLAN.md)
- [backend/app/rag/citations](../../../../backend/app/rag/citations/PLAN.md)

## Các bước triển khai

- [ ] UICHAT-01: Xây danh sách conversation, tải lịch sử phân trang và gửi message với idempotency.
- [x] UICHAT-02a: Hiển thị queued/running/waiting_approval/terminal, connection và retry error state.
- [ ] UICHAT-02b: Hiển thị final answer/needs_input khi message API được triển khai WP-06.
- [ ] UICHAT-03: Hiển thị citation với title/section/page, xử lý nguồn bị thu hồi bằng thông báo không còn quyền.
- [ ] UICHAT-04: Thêm preview ticket, approve/reject/expired; sửa draft tạo luồng mới đúng API.
- [ ] UICHAT-05: Phục hồi run/approval sau refresh và kết nối memory/device context được phép.

## Điều kiện hoàn thành

- [ ] UC hỏi tài liệu, hỏi trạng thái và tạo ticket demo được qua UI.
- [ ] Double click approve/refresh/reconnect không tạo ticket trùng.
- [ ] Không hiển thị lời khẳng định ticket đã tạo khi backend chưa có receipt.
