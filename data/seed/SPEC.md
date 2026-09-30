# Đặc tả dữ liệu demo V1

Trạng thái: contract M0, chưa phải bộ fixture hoàn chỉnh. Schema máy đọc nằm tại
[`../manifests/seed.schema.json`](../manifests/seed.schema.json).

## Mục tiêu và phạm vi

Bộ seed tạo một công ty hư cấu, chạy demo độc lập và đủ dữ liệu dương/âm cho ownership,
ACL tài liệu, ticket, service status và hội thoại. Không dùng tài khoản, tài liệu nội bộ,
URL riêng hay dữ liệu cá nhân thật.

| Entity | Quy mô V1 | Bao phủ bắt buộc |
|---|---:|---|
| Department | 2 | `engineering`, `operations` |
| User | 6 | 2 employee Engineering, 1 employee Operations, 1 IT mỗi phòng ban, 1 admin |
| Device | 3–5 | Một employee có cả Ubuntu và Windows để kiểm tra scope theo thiết bị |
| Document | khoảng 20 | `company`, `department`, `it_only`; vi/en; version cũ/mới; ít nhất 3 PDF text |
| Service state | đúng 3 | `vpn`, `registry` (Docker Registry), `gitlab` |
| Ticket | 18 | `open`, `in_progress`, `resolved`; nhiều owner/department/severity |
| Conversation | 6–10 | answered, no-answer, approval/ticket và nguồn bị cấm theo ACL |

## Quy ước định danh và tham chiếu

- File seed dùng stable key dạng kebab-case; không commit UUID database.
- Seed command map stable key sang UUID và upsert theo natural key trong một transaction.
- Mọi `*_key` phải tham chiếu entity tồn tại. Owner của device/conversation/ticket phải là
  user active; device được chọn phải thuộc owner hội thoại; department của ticket phải
  trùng department của owner tại thời điểm seed.
- `document_key + version_label` là identity của version. `source_document_keys` trong
  message chỉ tham chiếu tài liệu actor có quyền đọc tại timestamp hội thoại.
- Validator semantic của seed command phải kiểm tra unique key, foreign key, ba service ID,
  timestamp UTC, checksum/path và các ràng buộc chéo mà JSON Schema không diễn đạt được.

## ACL và tài liệu

- `visibility=department` bắt buộc `department_key`; `company` và `it_only` bắt buộc null.
- `it_only` chỉ xuất hiện trong hội thoại của IT/admin. Negative case giữ câu hỏi nhưng
  không gắn source bị cấm vào expected assistant message.
- Corpus mặc định là nội dung tự viết. Nếu dùng tài liệu công khai, manifest bắt buộc có
  license/provenance và checksum `sha256:<64 hex>`; source path luôn tương đối dưới
  `data/knowledge`.
- Hai version cùng document phải có khoảng hiệu lực rõ; version hết hạn không được dùng làm
  hướng dẫn hiện hành nhưng vẫn có thể làm lịch sử được phép đọc.

## Ticket, dịch vụ và hội thoại

- Ticket không có enum `reopened`: reopen là event chuyển từ `resolved` về `open` hoặc
  `in_progress`. Fixture V1 chỉ seed trạng thái hiện tại; event history viết ở WP-08.
- `resolution_note` bắt buộc về mặt semantic khi status là `resolved`, null với ticket chưa
  resolved. Không seed `approval_id`; ticket demo có nguồn `seed`, còn ticket do agent tạo
  sau này phải đi qua approval transaction.
- Mỗi service được trả ra API/tool với `source=simulated_monitor`. `fault_mode` là cơ chế mô
  phỏng lỗi dependency, tách khỏi trạng thái nghiệp vụ `healthy/degraded/down/unknown`.
- Conversation chỉ chứa lịch sử hiển thị được. Không lưu hidden reasoning, raw prompt,
  checkpoint hoặc payload tool nội bộ trong seed.

## Bảo mật, memory và thời gian

- Password không nằm trong JSON. Seed command đọc `DEMO_SEED_PASSWORD`, hash tại runtime và
  từ chối chạy nếu trống; log không in password/hash.
- Memory luôn active cho mọi user; seed không tạo candidate hoặc confirmed fact.
- Timestamp là ISO-8601 UTC, cố định để dữ liệu tái lập. Kịch bản cần “hiện tại” dùng clock
  injection ở test thay vì sửa fixture theo ngày chạy.
- Nội dung không chứa API key, token, cookie, email thật hoặc thông tin định danh cá nhân.

## Bố cục fixture khi triển khai WP-04

Manifest có thể tách thành `company.json`, `departments.json`, `users.json`, `devices.json`,
`documents.json`, `service_states.json`, `tickets.json`, `conversations.json`; seed command
ghép và validate thành document theo schema trước khi ghi DB. Thứ tự ghi là department →
user → device/document/service → ticket → conversation/message.

Seed có `--dry-run`, summary số record tạo/cập nhật/không đổi và không cung cấp reset cho
database đang sử dụng. Test cần database sạch phải dùng database/volume tạm biệt lập. Chạy
cùng manifest hai lần phải không tạo bản sao; thay đổi
stable key được coi là record mới, không phải rename ngầm.

## Tiêu chí nghiệm thu dữ liệu hoàn chỉnh

- JSON Schema và semantic references đều hợp lệ; checksum trùng file và không có path escape.
- Có negative case khác owner, khác department, employee đọc `it_only` và câu hỏi no-answer.
- Có ít nhất một user hai thiết bị, ticket ở cả ba trạng thái và service ở cả ba fault mode.
- Chạy seed hai lần cho cùng số record; reset guard được test; không tự tạo confirmed memory.
