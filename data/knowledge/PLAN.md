# Knowledge corpus — nội dung tài liệu demo

Trạng thái: corpus Markdown M2 được seed, ingest bằng fake embedding và publish; PDF fixtures vẫn được tạo riêng trong test parser.
Work packages: WP-01, WP-04, WP-05, WP-13.
Nguồn: [kế hoạch tổng](../../plan.md), mục 6, 8, 19; [thứ tự triển khai](../../docs/implementation-roadmap.md).

## Mục tiêu

Tự viết corpus Việt/Anh về chính sách IT giả lập có bằng chứng rõ để kiểm tra RAG.

## Hợp đồng và trách nhiệm

- Mục tiêu khoảng 20 tài liệu và ít nhất ba PDF text; PDF source phải thuộc dữ liệu tự tạo hoặc có quyền sử dụng.
- Bao phủ company/department/it_only, version cũ/mới và câu hỏi không có đáp án.
- Nội dung là chính sách hư cấu của công ty demo, không hướng dẫn hoặc mật khẩu của công ty thật.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `vpn-setup.md`
- `vpn-troubleshooting.md`
- `docker-registry.md`
- `gitlab-access.md`
- `it-escalation.md`
- `pdf/`
- `README.md`

## Phụ thuộc và phối hợp

- [data/manifests](../manifests/PLAN.md)
- [backend/app/rag/ingestion](../../backend/app/rag/ingestion/PLAN.md)
- [evals/cases](../../evals/cases/PLAN.md)

## Các bước triển khai

- [x] KNOW-01: Viết danh mục tài liệu theo issue/visibility và required facts dùng đánh giá.
- [ ] KNOW-02: Soạn Markdown trước, chuẩn bị ít nhất ba PDF có text với page mapping ổn định.
- [x] KNOW-03: Tạo cặp version thay đổi chính sách để test current-version và expiry.
- [ ] KNOW-04: Đặt tài liệu độc hại/malformed dành test trong fixture cô lập, không publish corpus demo mặc định.
- [x] KNOW-05: Review tính nhất quán giữa hướng dẫn, service ids, severity và quy trình ticket.

## Điều kiện hoàn thành

- [ ] Mọi tài liệu có metadata manifest và checksum; không có secret/PII thật.
- [ ] Bộ câu hỏi answerable có evidence span; no-answer không vô tình xuất hiện đáp án trong corpus.
- [ ] Citation tới trang/section đúng và ingestion không cần OCR.
