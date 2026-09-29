# PLAN gap audit — 2026-09-17

Audit này đối chiếu toàn bộ `**/PLAN.md` với code, migration và tests hiện có. Một ô chỉ được
đánh dấu hoàn thành khi có implementation và bằng chứng kiểm tra tương ứng. Tại thời điểm audit
còn 93 checkbox mở; con số này không đồng nghĩa 93 feature bắt buộc cho demo vì gồm cả điều
kiện release bên ngoài, mục tùy chọn và các quyết định kiến trúc có điều kiện.

## Đã bổ sung trong đợt audit

- Prompt assets có version/checksum và schema structured reply; OpenAI adapter dùng prompt đã khóa.
- Hybrid retrieval/evidence threshold, regression câu hỏi VPN tự nhiên và re-index command có dry-run/budget guard.
- Ticket device ownership được chặn tại approval, execution và composite database constraint.
- Shared frontend API client có timeout, safe errors, Retry-After và global session-expiry handling.
- Frontend error boundary, 404 fallback và cache cleanup khi session hết hạn.
- Approval maintenance job expire draft theo batch, cancel waiting run và phát event idempotent.
- Authenticated citation excerpt/download recheck current version và ACL; revoke trả 404.
- Semantic chunker giữ heading/paragraph/code block; eval evidence map theo stable corpus span.
- Evaluation cases khóa vào corpus snapshot và validator kiểm tra document/version/section/span.
- Budget concurrency gate tính reservation đang bay và chặn provider trước paid call.
- User cancel hỗ trợ optimistic version, idempotent replay và làm hết hiệu lực approval pending
  trong cùng transaction.
- Support graph đã route hai read tools theo model decision; OpenAI mapping giữ provider call ID,
  còn actor/run chỉ do server inject vào MCP stdio.
- Memory extraction chuyển thành durable background job: final message/run/job commit trước khi
  enqueue, pending job được reconciliation redeliver và replay không nhân đôi candidate.
- Agent context đọc conversation history thật, tách suggested/confirmed steps, loại history trái
  ACL và gắn nhãn historical cho citation dùng version superseded còn được phép đọc.
- Chat có thể tạo ticket proposal qua graph, phục hồi approval card sau refresh và chỉ hiển thị
  ticket ID sau khi approved write trả receipt từ database; draft hết hạn bị vô hiệu hóa trên UI.

## Thiếu thật — ưu tiên P0

1. Hoàn thiện phần còn lại của Chat context (`UICHAT-05`): UI chọn device/memory context;
   preview/approve/reject/edit/expired/refresh/receipt đã có.
2. Chuẩn hóa backend error envelope và cursor pagination (`API-05`, `REPO-04`).

## Thiếu thật — ưu tiên P1

1. PDF parsing subprocess có timeout/resource limits (`ING-03`).
2. Usage aggregate/report endpoint (`COST-05`) và observability spans/redaction/outage tests.
3. Ticket detail/filter và thống nhất query invalidation trên frontend.
4. Shared accessible dialog cho các thao tác xác nhận/destructive.
5. OpenAPI → TypeScript contract check và backend response-model completeness.
6. Retention cleanup jobs và query-plan evidence cho tập dữ liệu lớn.

## Cần bằng chứng môi trường, chưa được phép tuyên bố hoàn thành

- Live OpenAI re-index và retrieval baseline với `text-embedding-3-small`.
- Ba live evaluation repetitions, cost/variance report và human rubric review.
- Remote GitHub Actions, browser E2E lặp lại trên CI và artifacts khi job fail.
- Worker/Redis restart drill trên full stack.
- Clean-machine independent review, demo video và release sign-off.

## Bằng chứng local của đợt audit

- Backend unit + contract suite: pass toàn bộ.
- Backend integration suite: pass toàn bộ trên PostgreSQL/Redis test cô lập; chỉ
  `test_langgraph_checkpoint_spike` skip vì không cấp `CHECKPOINT_DATABASE_URL` riêng cho spike.
- Frontend: typecheck, lint, 23 tests và production build đều pass.
- Evaluation schema: 120 cases hợp lệ; fake development run đạt 80/80 deterministic checks.
- Không chạy live OpenAI, paid re-index, remote GitHub Actions hoặc browser E2E.

## Mục có điều kiện hoặc tạm hoãn

- MCP write không cần expose nếu ticket write tiếp tục ở application worker; MCP hiện chỉ là
  allowlisted read boundary.
- Citation relation table và global `corpus_revision` chỉ cần khi query/audit hoặc cross-process
  cache thực sự yêu cầu.
- Production DB role split và deploy server giữ mở theo quyết định tạm hoãn deployment.
- Ba PDF corpus không bắt buộc cho demo hiện tại vì corpus tự viết dùng Markdown và PDF upload đã
  có fixture an toàn; nếu dùng để trình diễn page citation thì cần bổ sung asset tự viết riêng.

## Quy tắc tiếp tục

Mỗi nhóm P0/P1 nên là một commit độc lập, có PLAN checkbox, regression test và command kiểm tra.
Không chạy paid/live command nếu chưa bật cờ opt-in; không sửa báo cáo lịch sử để giả thành bằng
chứng mới.
