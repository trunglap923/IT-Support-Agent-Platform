# UI — quản lý tài liệu và phiên bản

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-11.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 6, 7, 8, 14, 17; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Cho admin upload, theo dõi xử lý và publish kiến thức có kiểm soát.

## Hợp đồng và trách nhiệm

- Phân biệt document/version và processing/ready/published/failed; ready không tự thành current.
- Upload chỉ PDF text và Markdown trong giới hạn backend; cảnh báo PDF scan không hỗ trợ.
- UI không cung cấp URL crawler; publish/archive/đổi ACL cần quyền admin.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `DocumentsPage.tsx`
- `UploadForm.tsx`
- `VersionDetail.tsx`
- `IngestionStatus.tsx`
- `AclForm.tsx`

## Phụ thuộc và phối hợp

- [backend/app/services/documents](../../../../backend/app/services/documents/PLAN.md)
- [backend/app/rag/ingestion](../../../../backend/app/rag/ingestion/PLAN.md)
- [frontend/src/api](../../api/PLAN.md)

## Các bước triển khai

- [ ] UIDOC-01: Xây upload multipart và validate kích thước/định dạng sớm để báo lỗi dễ hiểu.
- [ ] UIDOC-02: Hiển thị tiến độ job bằng polling endpoint đã có và retry lỗi được cho phép.
- [ ] UIDOC-03: Cho xem preview chunks/page/section và thông tin ACL trước khi publish.
- [ ] UIDOC-04: Thêm thao tác publish version, archive, đổi scope và thông báo ảnh hưởng citation cũ.

## Điều kiện hoàn thành

- [ ] Ingestion lỗi không làm mất version đang phục vụ.
- [ ] Employee/IT không gọi được admin mutation; admin đổi ACL có hiệu lực ở nguồn lẫn chat cũ.
