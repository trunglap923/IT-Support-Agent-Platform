# Dữ liệu — bộ demo độc lập

Trạng thái: đã có kế hoạch; chưa triển khai tính năng.
Work packages: WP-01, WP-04, WP-07, WP-13.
Nguồn: [kế hoạch tổng](../plan.md), mục 3, 6, 19; [thứ tự triển khai](../docs/implementation-roadmap.md).

## Mục tiêu

Quản lý dữ liệu giả có phiên bản, đủ kiểm thử ACL và các tình huống demo mà không cần dữ liệu doanh nghiệp thật.

## Hợp đồng và trách nhiệm

- Source fixture và tài liệu tự viết được commit; file upload runtime/password thật không thuộc thư mục này.
- Bộ demo một doanh nghiệp, hai phòng ban, ba nhóm vấn đề VPN/Docker/GitLab.
- Giữ snapshot/checksum để evaluation lặp lại trên đúng corpus.

## Tệp dự kiến khi viết code

Các tên dưới đây là đầu ra cần tạo; hiện tại thư mục chứa kế hoạch.

- `seed/`
- `knowledge/`
- `manifests/`

## Phụ thuộc và phối hợp

- [data/seed](seed/PLAN.md)
- [data/knowledge](knowledge/PLAN.md)
- [data/manifests](manifests/PLAN.md)

## Các bước triển khai

- [ ] DATA-01: Chốt identifiers ổn định, persona, thiết bị và vocabulary dùng chung.
- [ ] DATA-02: Tạo seed tối thiểu cho M1/M2 rồi mở rộng ticket và memory scenarios theo mốc.
- [ ] DATA-03: Kiểm tra không có secret/PII thật; ghi nguồn/license khi dùng PDF công khai.
- [ ] DATA-04: Tách seed demo, test fixture và eval reset để không phá dữ liệu đang dùng.

## Điều kiện hoàn thành

- [ ] Seed chạy lại không nhân đôi dữ liệu hoặc tự ghi đè dữ liệu runtime đã thay đổi.
- [ ] Demo không phụ thuộc API VPN/GitLab/Jira hay tài liệu private.
