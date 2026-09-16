# Backup and restore drill

## Tạo backup

Stack cần có migration hiện hành. Chạy:

```bash
make backup
```

Mỗi bundle nằm dưới `backups/<UTC timestamp>-<pid>/` và gồm:

- `database.dump`: PostgreSQL custom-format dump;
- `database-counts.json`: Alembic revision và row counts quan trọng;
- `documents.tar.gz`: document storage archive;
- `documents.json`: đường dẫn, kích thước và SHA-256 từng file;
- `manifest.json`: checksum/kích thước các artifact, source metadata và restore policy.

`backups/` bị Git ignore. Hãy mã hóa và chuyển bundle ra storage có retention policy nếu dùng ngoài local demo.

## Kiểm tra restore an toàn

```bash
make restore-test
# hoặc
make restore-test BACKUP_DIR=backups/20260916T120000Z-12345
```

Restore drill kiểm tra checksum trước, tạo database `restore_test_*` và Docker volume `it-support-restore-*-documents`, restore vào hai target tạm, so row counts/Alembic revision và inventory tài liệu, sau đó luôn xóa target tạm bằng trap. Script từ chối bundle nằm ngoài thư mục `backups/`.

## Giới hạn khôi phục

- Bundle không gồm Redis vì Redis chỉ chứa queue/cache/lease có thể reconciliation; PostgreSQL là nguồn dữ liệu bền vững.
- Row-count và checksum verification phát hiện thiếu/hỏng artifact, nhưng không thay thế application-level recovery test cho mọi quan hệ nghiệp vụ.
- Backup local không mã hóa và không tự upload; không dùng nó làm chính sách production nếu chưa bổ sung encryption, remote retention, monitoring và định kỳ diễn tập.
- Database dump và document archive không tạo distributed snapshot; khi có upload/write đồng thời cần quiesce application trước khi backup production.
- Không có lệnh restore vào database phát triển/production. Việc phục hồi thật phải là runbook riêng, có maintenance window và xác nhận target rõ ràng.
