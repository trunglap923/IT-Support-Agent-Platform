# Roadmap triển khai và mục lục kế hoạch module

Nguồn yêu cầu: [plan.md](../plan.md), đặc biệt mục 21.1. Bản đồ trách nhiệm: [architecture.md](architecture.md).

## Trạng thái khởi tạo

- [x] Tạo cây thư mục kiến trúc và 57 file `PLAN.md`.
- [x] Mỗi module có hợp đồng, tệp cần viết, liên kết phối hợp, checklist và điều kiện hoàn thành.
- [x] Có README, bản đồ kiến trúc, ADR cấu trúc, kịch bản demo và cấu hình mẫu không chứa secret.
- [x] WP-01: runtime/dependencies, lockfiles và local install/lint/typecheck/test/build đã đạt; chờ CI remote đầu tiên sau push.
- [x] M0: hoàn tất spike provider/MCP/checkpointer, seed spec và 30 evaluation cases.

WP-01 và compatibility M0 đã hoàn thành ở local; WP-02..WP-14 chưa hoàn thành. Responses
live, MCP stdio, PostgreSQL checkpointer, seed contract và 30 evaluation cases đều có bằng
chứng. Paid/live checks vẫn là opt-in và không chạy trong CI.

## Cách dùng kế hoạch

1. Chọn WP nhỏ nhất có các điều kiện phụ thuộc đã đủ; đọc dòng tương ứng bên dưới.
2. Mở các `PLAN.md` liên quan, chỉ làm checklist thuộc phần đang triển khai. Một module có thể được bổ sung qua nhiều WP.
3. Tạo code, migration và test trong cùng lát cắt; ghi bằng chứng lệnh/test/report ở phần điều kiện hoàn thành khi làm xong.
4. Nếu phát hiện hợp đồng sai/thiếu, sửa [kế hoạch tổng](../plan.md) và module liên quan; thay đổi kiến trúc ghi [ADR](adr/PLAN.md).
5. Đánh dấu checklist theo mã như `APR-03` khi đã kiểm chứng, không tick chỉ vì đã tạo tên file.

“Phụ thuộc và phối hợp” trong PLAN gồm cả module tiêu thụ và test liên quan, có thể trỏ qua lại. Đó không phải thứ tự build; phụ thuộc WP trong bảng dưới mới là điều kiện triển khai. Chưa cần dựng mọi abstraction hoặc mọi bảng DB ngay WP-01.

## Điểm bắt đầu: WP-01 và M0

- [x] Kiểm tra Python 3.12/uv, Node LTS/npm và Docker Compose; phiên bản thực tế được ghi trong ADR-0002.
- [x] Khởi tạo `backend/pyproject.toml` và `frontend/package.json`, chọn phiên bản tương thích rồi tạo lockfiles bằng package manager.
- [x] Tạo backend app factory/config/health tối thiểu và frontend shell/router; chưa thêm nghiệp vụ chưa dùng.
- [x] Thiết kế fake-provider config để tests không cần paid keys; OpenAI mode fail rõ khi thiếu key và chưa được gọi từ API.
- [ ] Trước paid embedding/chat đầu tiên, bắt buộc nối DB/budget guard; phần này thuộc WP-04/WP-06.
- [x] Kiểm chứng Responses plain/structured/tool contract offline với strict schema và token cap.
- [x] Chạy Responses live bằng target opt-in; CI không có key và không chạy paid spike.
- [x] Smoke-test MCP stdio discovery/call và actor isolation qua hai subprocess.
- [x] Smoke-test PostgreSQL checkpointer pause/restart/resume qua hai process.
- [x] Viết seed spec và 30 evaluation cases đầu. Đây là công việc M0, không đợi tới WP-13 mới thiết kế cách chấm.
- [x] Cung cấp lint/typecheck/test/build commands có thực thi, CI fake-mode ban đầu; cách chạy và kết quả local đã ghi trong README/ADR-0002.

Không tự chạy paid evaluation hoặc kết nối dịch vụ doanh nghiệp thật từ lệnh bootstrap.

WP-04 cần embedding provider và usage ledger tối thiểu ngay trước paid ingestion đầu tiên; không đợi đến WP-06 mới bảo vệ ngân sách. WP-06 hoàn thiện generate/chat. Migrations được tạo từng phần theo consumer: ticket/service status reads cần schema ở WP-07, approval/write constraints ở WP-08, memory ở WP-12.

## Work packages

| WP | Phần việc | Phụ thuộc | Đầu ra kiểm chứng |
|---|---|---|---|
| WP-01 | Nền tảng, lock deps, env/lint và thử tích hợp | — | Fresh install/build; config sai báo rõ; compatibility spike M0. |
| WP-02 | Identity, conversation/run schema, session/CSRF | WP-01 | Login và wrong-owner/CSRF tests; DB constraints ban đầu. |
| WP-03 | Celery, trạng thái run/event store và SSE | WP-02 | Commit/enqueue/read/reconnect không tạo run mới; fake-mode CI. |
| WP-04 | Seed và parse/chunk/embed tài liệu draft | WP-01, WP-02 | Giữ metadata/page; ingest lại không nhân đôi; lỗi parse rõ. |
| WP-05 | Hybrid retrieval có scope và nguồn tham khảo | WP-04 | Company/department/IT-only; no-answer baseline; nguồn hiện hành. |
| WP-06 | RAG graph, provider/context, chat demo và trace | WP-03, WP-05 | UC-01/03 end-to-end, bounded loop, citations và Langfuse. |
| WP-07 | Business read services và MCP | WP-02 | Actor context từ server; service allowlist; chỉ đọc ticket của mình. |
| WP-08 | Approval, graph resume và ticket transaction | WP-03, WP-06, WP-07 | Double approve/replay/timeout/sai arguments; write có receipt. |
| WP-09 | Approval card, ticket cá nhân và IT UI | WP-08 | Browser E2E tạo/resolve/reopen; manual draft cùng approval path. |
| WP-10 | Recovery/reconcile và tình huống lỗi | WP-08 | Redis enqueue race; crash sau commit; lease/lock/receipt recovery. |
| WP-11 | Quản lý tài liệu/versioning/ACL đầy đủ | WP-05 | Upload → preview → publish; revoked ACL không rò source/history. |
| WP-12 | Memory lifecycle/context và settings UI | WP-06, WP-09 | Consent/confirm/device isolation; delete-while-job-running. |
| WP-13 | Evaluation/feedback/performance/cost | WP-09, WP-10, WP-11, WP-12 | 120 ca; báo cáo G-01..G-09 có mẫu số/phương pháp/failures. |
| WP-14 | Bàn giao và kiểm chứng tái lập | WP-13 | G-10: máy sạch, restore target test, demo/release checklist. |

### Module cần mở theo WP

- **WP-01**: [Backend Python](../backend/PLAN.md); [Frontend — ứng dụng web demo](../frontend/PLAN.md); [Model và embedding adapters](../backend/app/providers/PLAN.md); [ADR — quyết định kiến trúc và kết quả thử tích hợp](adr/PLAN.md); [CI — kiểm tra chất lượng không cần API trả phí](../.github/workflows/PLAN.md).
- **WP-02**: [Schema và DB sessions](../backend/app/db/PLAN.md); [Database migrations](../backend/migrations/PLAN.md); [Đăng nhập và phân quyền](../backend/app/auth/PLAN.md); [Conversation, run và event store](../backend/app/services/conversations/PLAN.md); [UI — đăng nhập và phiên người dùng](../frontend/src/features/auth/PLAN.md).
- **WP-03**: [Workers, scheduler và recovery](../backend/app/jobs/PLAN.md); [HTTP API và SSE](../backend/app/api/PLAN.md); [Frontend — HTTP client và sự kiện run](../frontend/src/api/PLAN.md); [Integration và failure tests](../backend/tests/integration/PLAN.md); [Infrastructure — môi trường local và vận hành](../infra/PLAN.md).
- **WP-04**: [Dữ liệu — bộ demo độc lập](../data/PLAN.md); [Nhập và trích xuất tài liệu](../backend/app/rag/ingestion/PLAN.md); [Chia đoạn tài liệu](../backend/app/rag/chunking/PLAN.md); [Xuất bản tài liệu và ACL](../backend/app/services/documents/PLAN.md).
- **WP-05**: [Tìm kiếm hybrid có phân quyền](../backend/app/rag/retrieval/PLAN.md); [Citation và output evidence](../backend/app/rag/citations/PLAN.md); [Queries và data access](../backend/app/repositories/PLAN.md); [Evaluation — đo chất lượng và điều kiện release](../evals/PLAN.md).
- **WP-06**: [LangGraph runtime](../backend/app/agent/PLAN.md); [Context và compaction](../backend/app/agent/context/PLAN.md); [Model và embedding adapters](../backend/app/providers/PLAN.md); [Ngân sách và usage ledger](../backend/app/services/budget/PLAN.md); [Logs, trace và feedback telemetry](../backend/app/observability/PLAN.md); [UI — chat, nguồn tham khảo và approval](../frontend/src/features/chat/PLAN.md).
- **WP-07**: [Ticket và hàng đợi IT](../backend/app/services/tickets/PLAN.md); [Trạng thái dịch vụ giả lập](../backend/app/services/service_status/PLAN.md); [MCP server nội bộ](../backend/app/mcp_server/PLAN.md); [Tool schema, registry và executor](../backend/app/tools/PLAN.md); [Contract tests](../backend/tests/contract/PLAN.md).
- **WP-08**: [Draft và xác nhận hành động](../backend/app/services/approvals/PLAN.md); [Ticket và hàng đợi IT](../backend/app/services/tickets/PLAN.md); [LangGraph runtime](../backend/app/agent/PLAN.md); [MCP server nội bộ](../backend/app/mcp_server/PLAN.md); [Integration và failure tests](../backend/tests/integration/PLAN.md).
- **WP-09**: [UI — chat, nguồn tham khảo và approval](../frontend/src/features/chat/PLAN.md); [UI — ticket cá nhân và xử lý của IT](../frontend/src/features/tickets/PLAN.md); [UI — trạng thái dịch vụ mô phỏng](../frontend/src/features/services/PLAN.md); [Kiểm thử trình duyệt end-to-end](../frontend/e2e/PLAN.md).
- **WP-10**: [Workers, scheduler và recovery](../backend/app/jobs/PLAN.md); [Conversation, run và event store](../backend/app/services/conversations/PLAN.md); [Draft và xác nhận hành động](../backend/app/services/approvals/PLAN.md); [Ticket và hàng đợi IT](../backend/app/services/tickets/PLAN.md); [Integration và failure tests](../backend/tests/integration/PLAN.md).
- **WP-11**: [Xuất bản tài liệu và ACL](../backend/app/services/documents/PLAN.md); [RAG và knowledge lifecycle](../backend/app/rag/PLAN.md); [UI — quản lý tài liệu và phiên bản](../frontend/src/features/documents/PLAN.md); [Kiểm thử trình duyệt end-to-end](../frontend/e2e/PLAN.md).
- **WP-12**: [Memory qua nhiều cuộc trò chuyện](../backend/app/memory/PLAN.md); [Context và compaction](../backend/app/agent/context/PLAN.md); [UI — quản lý trí nhớ có đồng ý](../frontend/src/features/memory/PLAN.md); [Workers, scheduler và recovery](../backend/app/jobs/PLAN.md); [Integration và failure tests](../backend/tests/integration/PLAN.md).
- **WP-13**: [Evaluation — đo chất lượng và điều kiện release](../evals/PLAN.md); [Evaluation runner — chạy, chấm và lưu bằng chứng](../evals/runner/PLAN.md); [Logs, trace và feedback telemetry](../backend/app/observability/PLAN.md); [Báo cáo — kết quả đo và bằng chứng portfolio](../reports/PLAN.md).
- **WP-14**: [Tài liệu — điều hướng và bàn giao dự án](PLAN.md); [ADR — quyết định kiến trúc và kết quả thử tích hợp](adr/PLAN.md); [Infrastructure — môi trường local và vận hành](../infra/PLAN.md); [Báo cáo — kết quả đo và bằng chứng portfolio](../reports/PLAN.md).

## Mốc kiểm tra sản phẩm

| Mốc | Trọng tâm | Điều kiện trước khi đi tiếp |
|---|---|---|
| M0 | Khung runtime và thử tích hợp | Có lockfiles/compatibility evidence, seed spec, 30 cases |
| M1 | DB/auth, web shell, queues/CI | Login/ownership và run status hoạt động |
| M2 | RAG/chat/SSE/citations/Langfuse | Demo hỏi tài liệu end-to-end; baseline đầu tiên |
| M3 | MCP, approval/ticket và UI | Xác nhận đúng một ticket, đúng quyền |
| M4 | Recovery + document admin | Restart/retry/ACL/versioning có test |
| M5 | Memory có đồng ý | Cross-conversation/device/epoch tests đạt |
| M6 | Evaluation và báo cáo | Đủ 120 cases, số đo gate/latency/cost |
| M7 | Hoàn thiện và bàn giao | Máy sạch/restore/demo/Definition of Done |

Ưu tiên WP-01..WP-06 cho demo M2. WP-07 có thể làm sau WP-02 nhưng không cần kéo dài đường tới demo RAG. Tài liệu, test, quyền dữ liệu và telemetry được viết cùng feature; WP-13 là tổng hợp evaluation đầy đủ, không phải lúc bắt đầu viết test.

Ước lượng thời gian vẫn theo mục 21 của kế hoạch tổng; chỉ cập nhật sau khi có thời gian thực tế. Không thay mốc V1 bằng demo trung gian nếu thiếu MCP/LangGraph/memory/Redis/Langfuse.

## Mục lục đầy đủ: 57 kế hoạch

### Backend — nền tảng và adapters

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `backend` | [Backend Python](../backend/PLAN.md) | WP-01, WP-02 |
| `backend/app` | [Composition root và cấu hình](../backend/app/PLAN.md) | WP-01, WP-02, WP-03 |
| `backend/app/api` | [HTTP API và SSE](../backend/app/api/PLAN.md) | WP-02, WP-03, WP-08, WP-11, WP-12 |
| `backend/app/auth` | [Đăng nhập và phân quyền](../backend/app/auth/PLAN.md) | WP-02, WP-05, WP-08 |
| `backend/app/memory` | [Memory qua nhiều cuộc trò chuyện](../backend/app/memory/PLAN.md) | WP-12 |
| `backend/app/tools` | [Tool schema, registry và executor](../backend/app/tools/PLAN.md) | WP-06, WP-07, WP-08 |
| `backend/app/mcp_server` | [MCP server nội bộ](../backend/app/mcp_server/PLAN.md) | WP-07, WP-08, WP-10 |
| `backend/app/repositories` | [Queries và data access](../backend/app/repositories/PLAN.md) | WP-02, WP-05, WP-07, WP-11, WP-12 |
| `backend/app/db` | [Schema và DB sessions](../backend/app/db/PLAN.md) | WP-02, WP-03, WP-04, WP-07, WP-08, WP-12 |
| `backend/migrations` | [Database migrations](../backend/migrations/PLAN.md) | WP-02, WP-04, WP-07, WP-08, WP-12, WP-14 |
| `backend/app/providers` | [Model và embedding adapters](../backend/app/providers/PLAN.md) | WP-01, WP-04, WP-06, WP-12, WP-13 |
| `backend/app/jobs` | [Workers, scheduler và recovery](../backend/app/jobs/PLAN.md) | WP-03, WP-04, WP-08, WP-10, WP-12 |
| `backend/app/observability` | [Logs, trace và feedback telemetry](../backend/app/observability/PLAN.md) | WP-03, WP-04, WP-06, WP-13 |
| `backend/app/prompts` | [Prompt và output schema](../backend/app/prompts/PLAN.md) | WP-06, WP-12, WP-13 |

### Backend — agent và context

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `backend/app/agent` | [LangGraph runtime](../backend/app/agent/PLAN.md) | WP-06, WP-08, WP-10, WP-12 |
| `backend/app/agent/context` | [Context và compaction](../backend/app/agent/context/PLAN.md) | WP-06, WP-12 |

### Backend — RAG

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `backend/app/rag` | [RAG và knowledge lifecycle](../backend/app/rag/PLAN.md) | WP-04, WP-05, WP-11 |
| `backend/app/rag/ingestion` | [Nhập và trích xuất tài liệu](../backend/app/rag/ingestion/PLAN.md) | WP-04, WP-11 |
| `backend/app/rag/chunking` | [Chia đoạn tài liệu](../backend/app/rag/chunking/PLAN.md) | WP-04, WP-05 |
| `backend/app/rag/retrieval` | [Tìm kiếm hybrid có phân quyền](../backend/app/rag/retrieval/PLAN.md) | WP-05, WP-13 |
| `backend/app/rag/citations` | [Citation và output evidence](../backend/app/rag/citations/PLAN.md) | WP-05, WP-06, WP-11 |

### Backend — business services

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `backend/app/services` | [Business services](../backend/app/services/PLAN.md) | WP-02, WP-07, WP-08, WP-11, WP-12 |
| `backend/app/services/conversations` | [Conversation, run và event store](../backend/app/services/conversations/PLAN.md) | WP-02, WP-03, WP-06, WP-10 |
| `backend/app/services/approvals` | [Draft và xác nhận hành động](../backend/app/services/approvals/PLAN.md) | WP-08, WP-10 |
| `backend/app/services/tickets` | [Ticket và hàng đợi IT](../backend/app/services/tickets/PLAN.md) | WP-07, WP-08, WP-09, WP-10 |
| `backend/app/services/documents` | [Xuất bản tài liệu và ACL](../backend/app/services/documents/PLAN.md) | WP-04, WP-05, WP-11 |
| `backend/app/services/budget` | [Ngân sách và usage ledger](../backend/app/services/budget/PLAN.md) | WP-04, WP-06, WP-12, WP-13 |
| `backend/app/services/service_status` | [Trạng thái dịch vụ giả lập](../backend/app/services/service_status/PLAN.md) | WP-07, WP-10 |

### Backend — kiểm thử

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `backend/tests` | [Chiến lược kiểm thử backend](../backend/tests/PLAN.md) | WP-01, WP-02, WP-03, WP-13 |
| `backend/tests/unit` | [Unit tests](../backend/tests/unit/PLAN.md) | WP-02, WP-04, WP-06, WP-08, WP-12 |
| `backend/tests/integration` | [Integration và failure tests](../backend/tests/integration/PLAN.md) | WP-02, WP-03, WP-05, WP-08, WP-10, WP-12 |
| `backend/tests/contract` | [Contract tests](../backend/tests/contract/PLAN.md) | WP-01, WP-06, WP-07, WP-08 |

### Frontend

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `frontend` | [Frontend — ứng dụng web demo](../frontend/PLAN.md) | WP-01, WP-06, WP-09, WP-11, WP-12 |
| `frontend/src` | [Frontend — composition và router](../frontend/src/PLAN.md) | WP-01, WP-06, WP-09 |
| `frontend/src/api` | [Frontend — HTTP client và sự kiện run](../frontend/src/api/PLAN.md) | WP-02, WP-03, WP-06, WP-09 |
| `frontend/src/components` | [Frontend — thành phần dùng chung](../frontend/src/components/PLAN.md) | WP-01, WP-06, WP-09, WP-11, WP-12 |
| `frontend/src/features` | [Frontend — các khu vực chức năng](../frontend/src/features/PLAN.md) | WP-02, WP-06, WP-09, WP-11, WP-12 |
| `frontend/src/features/auth` | [UI — đăng nhập và phiên người dùng](../frontend/src/features/auth/PLAN.md) | WP-02 |
| `frontend/src/features/chat` | [UI — chat, nguồn tham khảo và approval](../frontend/src/features/chat/PLAN.md) | WP-06, WP-09, WP-12 |
| `frontend/src/features/tickets` | [UI — ticket cá nhân và xử lý của IT](../frontend/src/features/tickets/PLAN.md) | WP-09 |
| `frontend/src/features/documents` | [UI — quản lý tài liệu và phiên bản](../frontend/src/features/documents/PLAN.md) | WP-11 |
| `frontend/src/features/memory` | [UI — quản lý trí nhớ có đồng ý](../frontend/src/features/memory/PLAN.md) | WP-12 |
| `frontend/src/features/services` | [UI — trạng thái dịch vụ mô phỏng](../frontend/src/features/services/PLAN.md) | WP-07, WP-09 |
| `frontend/e2e` | [Kiểm thử trình duyệt end-to-end](../frontend/e2e/PLAN.md) | WP-06, WP-09, WP-11, WP-12, WP-13 |

### Dữ liệu

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `data` | [Dữ liệu — bộ demo độc lập](../data/PLAN.md) | WP-01, WP-04, WP-07, WP-13 |
| `data/seed` | [Seed — người dùng, thiết bị, ticket và dịch vụ](../data/seed/PLAN.md) | WP-01, WP-02, WP-04, WP-07, WP-12 |
| `data/knowledge` | [Knowledge corpus — nội dung tài liệu demo](../data/knowledge/PLAN.md) | WP-01, WP-04, WP-05, WP-13 |
| `data/manifests` | [Manifest — metadata, ACL và snapshot dữ liệu](../data/manifests/PLAN.md) | WP-01, WP-04, WP-05, WP-13 |

### Evaluation và báo cáo

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `evals` | [Evaluation — đo chất lượng và điều kiện release](../evals/PLAN.md) | WP-01, WP-05, WP-06, WP-13 |
| `evals/cases` | [Evaluation cases — dữ liệu kiểm thử có đáp án](../evals/cases/PLAN.md) | WP-01, WP-05, WP-06, WP-12, WP-13 |
| `evals/rubrics` | [Evaluation rubrics — cách chấm và release gates](../evals/rubrics/PLAN.md) | WP-01, WP-05, WP-13 |
| `evals/runner` | [Evaluation runner — chạy, chấm và lưu bằng chứng](../evals/runner/PLAN.md) | WP-05, WP-06, WP-13 |
| `reports` | [Báo cáo — kết quả đo và bằng chứng portfolio](../reports/PLAN.md) | WP-06, WP-13, WP-14 |

### Tài liệu, infrastructure và CI

| Module | Kế hoạch | WP liên quan |
|---|---|---|
| `docs` | [Tài liệu — điều hướng và bàn giao dự án](PLAN.md) | WP-01, WP-06, WP-14 |
| `docs/adr` | [ADR — quyết định kiến trúc và kết quả thử tích hợp](adr/PLAN.md) | WP-01, WP-06, WP-08, WP-12, WP-14 |
| `infra` | [Infrastructure — môi trường local và vận hành](../infra/PLAN.md) | WP-01, WP-02, WP-03, WP-10, WP-14 |
| `.github/workflows` | [CI — kiểm tra chất lượng không cần API trả phí](../.github/workflows/PLAN.md) | WP-01, WP-03, WP-09, WP-13, WP-14 |

## Quy tắc chống lệch kế hoạch

- `plan.md` hiện hành là nguồn schema/state/route/limit và scope. [Bản gốc lưu trữ](archive/plan-original.md) chỉ dùng tham khảo.
- Tên tệp dự kiến ở PLAN có thể tinh chỉnh trong lúc code, nhưng đổi hợp đồng phải cập nhật các module liên quan.
- Số lượng file kế hoạch không phải số package/service cần triển khai; giữ một backend codebase và một frontend.
- Chỉ ghi “đạt” cho feature/test/metric đã chạy và có bằng chứng. Live quality, fake testing và scaffold là ba trạng thái khác nhau.
