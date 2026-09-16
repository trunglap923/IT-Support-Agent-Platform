# Citation và output evidence

Trạng thái: source DTO, allowlist validation và no-answer baseline đã triển khai; ACL recheck lịch sử còn WP-06/WP-11.
Work packages: WP-05, WP-06, WP-11.
Nguồn: [kế hoạch tổng](../../../../plan.md), mục 8.3, 12.4, 17; [thứ tự triển khai](../../../../docs/implementation-roadmap.md).

## Mục tiêu

Bảo đảm câu trả lời chỉ tham chiếu source có thật và còn được phép xem.

## Hợp đồng và trách nhiệm

- Source DTO: source_id/document_id/version_id/chunk_id/title/page_number/section/excerpt.
- ID validity là kiểm tra bằng code; claim support được chấm riêng bằng rubric.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `sources.py`
- `validator.py`
- `history_visibility.py`

## Phụ thuộc và phối hợp

- [backend/app/services/documents](../../services/documents/PLAN.md)
- [backend/app/auth](../../auth/PLAN.md)
- [backend/app/agent/context](../../agent/context/PLAN.md)
- [evals/rubrics](../../../../evals/rubrics/PLAN.md)

## Các bước triển khai

- [x] CITE-01: Tạo source DTO từ chunks thực tế; không dùng URL/title model tự sinh.
- [x] CITE-02: Validate citation ID thuộc retrieval allowlist; ACL recheck cuối nối ở WP-06.
- [ ] CITE-03: Repair tối đa một lần trong run budget; nếu vẫn sai thì abstain/hỏi thêm.
- [ ] CITE-04: Nối message_sources để kiểm tra lại historical messages khi ACL thay đổi.
- [ ] CITE-05: Cấp download/excerpt qua authenticated API, archive/retired source có trạng thái rõ.

## Điều kiện hoàn thành

- [ ] Citation không tồn tại/sai version/sai quyền bị chặn.
- [ ] Rút ACL sau retrieval không làm lộ source trong answer hoặc lịch sử đọc lại.
- [ ] Markdown page=null; PDF page number bắt đầu từ 1; link source do server cấp.
