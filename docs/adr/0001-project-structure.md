# ADR-0001 — Monorepo và kế hoạch theo module

Ngày: 2026-09-15  
Trạng thái: chấp nhận cho cấu trúc thư mục; chưa xác nhận runtime/dependency compatibility.

## Bối cảnh

Một người làm portfolio, cần demo sớm và dễ chuyển kế hoạch tổng thành các đầu việc code nhỏ. Kiến trúc V1 đã chọn trong [plan.md](../../plan.md); người xây dựng yêu cầu khởi tạo thư mục cùng kế hoạch cho từng phần.

## Quyết định

- Dùng monorepo: backend Python, frontend TypeScript, data, evals, reports, docs và infra.
- Mỗi ranh giới chức năng có `PLAN.md` mô tả trách nhiệm, tệp dự kiến, dependency, checklist có ID và điều kiện hoàn thành.
- Chia nhỏ RAG, context, các business service và các trang web vì các phần này có hợp đồng/kiểm thử riêng. Các file trong một module vẫn có thể được tạo dần.
- [Roadmap](../implementation-roadmap.md) là thứ tự WP; [kế hoạch tổng](../../plan.md) là nguồn yêu cầu. Cross-links trong PLAN là quan hệ phối hợp, không áp đặt thứ tự tuyến tính.
- API, worker và MCP cùng package Python; không thêm microservice hoặc agent mới chỉ vì có thư mục riêng.
- Bộ khung ban đầu không tạo code giả, lockfile giả hay command rỗng. Runtime scaffold và smoke tests thuộc WP-01/M0.

## Hệ quả

Có nhiều file kế hoạch nhỏ nhưng không buộc triển khai cùng lúc. Thay đổi thiết kế phải cập nhật cả kế hoạch tổng và các module bị ảnh hưởng. Mỗi checkbox chỉ được tick sau khi có code/bằng chứng tương ứng.

Phiên bản dependency, khả năng model access, MCP stdio và PostgreSQL checkpointer sẽ được kiểm tra ở spike M0 và ghi trong ADR tiếp theo; ADR này không tuyên bố chúng đã chạy thành công.
