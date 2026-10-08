# Project handoff — IT Support Agent Platform

> Implementation snapshot base: 2026-09-17, Git `8806b61`, branch `main`.
> File này có thể nằm trong một docs-only commit mới hơn commit implementation đó.
>
> Dùng file này làm context đầu tiên cho một chat/agent mới. Sau đó đối chiếu Git status,
> commit mới hơn và các tài liệu được liên kết; không giả định snapshot này tự cập nhật.

## Prompt ngắn để mở chat mới

```text
Hãy đọc toàn bộ docs/project-handoff.md trước. Sau đó kiểm tra git status và các file liên quan
đến phần việc tôi yêu cầu. Giữ nguyên các ranh giới bảo mật, không reset database, không chạy
OpenAI/live/paid command nếu tôi chưa opt-in rõ ràng, và không đánh dấu PLAN hoàn thành nếu chưa
có implementation cùng bằng chứng test. Mỗi phần code độc lập nên là một commit nhỏ.
```

## 1. Mục tiêu sản phẩm

Đây là portfolio prototype cho một trợ lý IT nội bộ có trạng thái, không phải chatbot hỏi đáp
đơn giản. Phạm vi V1:

- Chat RAG trên tài liệu IT có citation và no-answer an toàn.
- Đọc trạng thái VPN, Docker Registry và GitLab qua governed tools/MCP.
- Đọc ticket đúng owner; tạo ticket bắt buộc có approval và receipt idempotent.
- IT queue có resolve/reopen; admin quản lý service status và tài liệu.
- Tài liệu có upload, version, publish/revoke và ACL company/department/IT-only.
- Memory luôn hoạt động qua nhiều conversation nhưng chỉ dùng fact đã được xác nhận.
- PostgreSQL/pgvector là nguồn trạng thái bền vững; Redis/Celery xử lý job và recovery.
- Fake mode chạy độc lập, deterministic và không cần API key; OpenAI/Langfuse là tùy chọn.

Tên portfolio đề xuất: **Stateful IT Support Agent with Evaluated RAG and Approval Workflows**.

## 2. Trạng thái hiện tại

- WP-01 đến WP-14 đã có implementation chính và local evidence.
- Alembic head: `0018_always_on_memory`.
- Stack Docker có 7 service: frontend, API, agent worker, background worker, scheduler,
  PostgreSQL/pgvector và Redis.
- Tại snapshot này, 7/7 service đang healthy.
- `.env` local đang dùng `TEXT_PROVIDER=fake` và `EMBEDDING_PROVIDER=fake`.
- Demo seed đã hội tụ: `created=0 updated=0 unchanged=43`.
- Seed knowledge: 9 document hiện hành, 11 versions, 41 chunks, chunker
  `semantic-window-v2`.
- Worktree sạch ngay trước khi tạo file handoff này.
- Chưa deploy server thật; CI không deploy.

Không được gọi dự án là production-ready. Release decision hiện vẫn **not ready** vì thiếu live,
human, remote-CI và một số operational evidence.

## 3. Kiến trúc runtime

```text
Browser → Nginx/React → FastAPI → PostgreSQL 17 + pgvector
                              ↘ Redis → Celery agent/background + scheduler
Agent worker → LangGraph → scoped hybrid RAG / governed tools
                                      ↘ MCP stdio → business services
                         ↘ fake hoặc OpenAI provider → optional Langfuse
```

Các ranh giới quan trọng:

- Browser/model không được cung cấp actor, role hoặc quyền truy cập đáng tin cậy.
- API/service/repository luôn scope theo principal lấy từ session phía server.
- LangGraph/model không ghi ticket trực tiếp.
- Ticket chỉ được ghi sau approval; unique receipt chống double approve/replay.
- Citation cuối chỉ được chọn từ source IDs do retrieval trả về.
- Redis delivery không được xem là exactly-once; PostgreSQL giữ state/event/receipt bền vững.
- Paid model/embedding call phải đi qua usage ledger và budget admission.

Xem [architecture.md](architecture.md) và
[ADR runtime](adr/0002-runtime-and-integration.md) để có chi tiết.

## 4. Những phần đã hoàn thành

### Nền tảng, auth và persistence

- FastAPI app factory, typed settings, health/live/ready và request IDs.
- React/Vite router, Nginx same-origin API proxy và frontend error boundary.
- PostgreSQL async SQLAlchemy, Alembic, pgvector và 17 migrations.
- Session-cookie login/logout/current-user, expiration, CSRF, secure cookie flags và RBAC.
- Account inactive bị từ chối ngay cả khi session cũ còn hạn.
- Conversation/run/event ownership, state machine, SSE cursor/reconnect và user cancellation.

### RAG và quản lý tài liệu

- Corpus IT tự viết, manifest/checksum/license validation.
- Markdown/PDF extraction, deterministic semantic chunking và fake/OpenAI embeddings.
- Idempotent ingestion; seed tự refresh completed jobs nếu parser/chunker/index metadata cũ.
- Hybrid PostgreSQL full-text + pgvector retrieval với ACL/current-version filters.
- Evidence threshold, no-answer và citation allowlist.
- Authenticated source excerpt/download; revoked hoặc trái ACL trả 404.
- Document upload/preview/process/publish/version/revoke/ACL và admin UI.
- Controlled `knowledge-reindex` có dry-run, paid opt-in và không reset database.

### Agent, tools và ticket workflow

- Bounded LangGraph support graph, structured provider contract và context budget.
- Context phân biệt assistant suggestion với bước user xác nhận đã thử.
- History có citation bị recheck ACL; superseded source được gắn nhãn historical.
- Governed tool registry/executor và MCP stdio với trusted actor context.
- Tool đọc service status và ticket của chính user.
- Ticket proposal → approval draft → checkpoint pause/resume → transactional write → receipt.
- Approval expiration, run cancellation, lease/retry/reconciliation và failure recovery.
- Frontend chat phục hồi approval sau refresh; receipt chỉ hiện sau DB write thành công.
- Employee ticket list, IT operations queue và admin service-status UI.

### Memory, observability và evaluation

- Always-on memory, candidate confirmation/rejection, device scope, edit/delete và epoch protection.
- Durable memory extraction job được commit trước enqueue; reconciliation replay idempotent.
- Langfuse adapter/no-op fake mode, feedback metadata, token usage và budget ledger.
- Evaluation dataset 120 cases, chia đều RAG/permission/tool/approval/memory/failure.
- Deterministic fake runner, guarded live runner, retrieval baseline và release reports.
- Production Dockerfiles, Compose, Make targets, backup và isolated restore test.
- GitHub Actions đã cấu hình migrations/integration/contracts/E2E/image/secret checks,
  nhưng chưa có remote run evidence trong snapshot này.

## 5. Fake mode và OpenAI mode — rất dễ hiểu sai

### Cấu hình hiện tại

```dotenv
TEXT_PROVIDER=fake
EMBEDDING_PROVIDER=fake
```

Trong cấu hình này **không có LLM tạo câu trả lời**:

- Fake tool router dùng so khớp cụm từ để chọn service/ticket/create-ticket tool.
- Fake RAG reply nối trực tiếp tối đa ba evidence excerpts.
- Vì corpus viết bằng tiếng Anh, câu trả lời RAG fake có thể là tiếng Anh.
- Service status, ticket list, approval message và ticket receipt được format deterministic
  trong Python.

Đây là behavior có chủ đích cho test/offline demo, không đại diện chất lượng LLM.

### Bật OpenAI text generation nhưng giữ embedding fake

```dotenv
TEXT_PROVIDER=openai
EMBEDDING_PROVIDER=fake
OPENAI_API_KEY=<secret>
```

Sau đó chạy `make up`. OpenAI sẽ chọn tool và tổng hợp structured RAG answer; citation và quyền
vẫn do server kiểm soát. Embedding không cần re-index trong cấu hình này.

Prompt chính nằm tại
[backend/app/prompts/agent.md](../backend/app/prompts/agent.md), được version/checksum trong
[prompt_manifest.json](../backend/app/prompts/prompt_manifest.json) và truyền vào Responses API
tại [openai.py](../backend/app/providers/openai.py). Prompt chọn tool hiện vẫn inline trong
`OpenAITextProvider.choose_support_tool`.

Nếu sửa prompt asset, phải cập nhật checksum manifest và chạy prompt/provider contract tests.
Prompt hiện chưa bắt buộc trả lời cùng ngôn ngữ với câu hỏi; đây là một cải tiến nên làm tiếp.

## 6. Demo data

Mọi demo account dùng password từ `DEMO_SEED_PASSWORD`; không ghi password thật vào tài liệu.

| Email | Role | Department |
|---|---|---|
| `employee.engineering@example.com` | employee | Engineering |
| `employee.engineering.second@example.com` | employee | Engineering |
| `employee.operations@example.com` | employee | Operations |
| `it.engineering@example.com` | IT | Engineering |
| `it.operations@example.com` | IT | Operations |
| `admin@example.com` | admin | Operations |

Seed còn có 3 devices, 3 service states, 18 tickets và knowledge corpus theo nhiều ACL. Seed là
idempotent và không có target reset phá hủy database đang dùng.

Manual smoke đã xác nhận:

- Câu hỏi Ubuntu/VPN tìm đúng tài liệu và citation.
- “Trạng thái VPN hiện tại thế nào?” trả service state hiện hành.
- “Cho tôi xem các ticket đang mở của tôi” chỉ trả ticket đúng owner.
- “Tạo ticket giúp tôi…” tạo approval draft; sau approve mới có ticket receipt.

## 7. Lệnh thường dùng

```bash
make demo                 # migrate + seed + start stack
make status               # xem trạng thái Compose
make down                 # dừng stack, giữ named volumes
make seed-dry-run         # preview, không persist
make seed                 # seed idempotent

make test                 # backend + isolated services + frontend checks
make test-e2e             # Playwright workflows
make eval                 # deterministic non-paid evaluation
make clean-verify         # fresh isolated stack verification
make docs-check           # kiểm tra relative Markdown links
```

Knowledge/OpenAI commands:

```bash
make knowledge-reindex-dry-run
RUN_PAID_REINDEX=1 make knowledge-reindex
make retrieval-baseline

RUN_OPENAI_LIVE_SPIKE=1 make spike-openai-live
TEXT_PROVIDER=openai RUN_LIVE_EVAL=1 make eval-agent-live
```

`eval-agent-live` tạo, migrate và dọn một PostgreSQL/pgvector container riêng; không cần đặt
`EVAL_DATABASE_URL` và không ghi ledger vào database development. Không chạy lệnh paid/live nếu
user chưa opt-in rõ ràng. Không log hoặc commit API key.

## 8. Bằng chứng kiểm thử gần nhất

Bằng chứng full-suite gần nhất trước audit:

- Backend unit + contract: pass toàn bộ.
- Backend integration trên PostgreSQL/Redis cô lập: pass toàn bộ; checkpoint spike skip khi
  không có `CHECKPOINT_DATABASE_URL` riêng.
- Frontend lint/typecheck, 23 tests và production build: pass.
- Evaluation schema: 120 cases hợp lệ; fake development: 80/80 deterministic checks.
- Trước đó Playwright có 7 deterministic journeys pass và clean-stack verification 7/7 healthy.

Bằng chứng sau fix `8806b61`:

- Ruff format/lint và mypy cho demo document seed: pass.
- `test_demo_document_seed.py`: 2 passed trên database cô lập.
- Seed nâng 11 stale versions từ `word-window-v1` lên `semantic-window-v2`.
- Lượt dry-run sau apply: `created=0 updated=0 unchanged=43`.
- Worker mới có tool router và đăng ký đủ run/approval/memory/reconciliation tasks.

Không diễn giải fake pass rate thành chất lượng semantic của model thật.

## 9. Việc cần làm tiếp theo

### P0 — nên làm trước

1. Cải thiện chat presentation:
   - SafeMarkdown allowlist thay vì plain text.
   - Không hiển thị raw Markdown heading.
   - Rút gọn citation excerpt để không lặp toàn bộ answer.
   - Giữ line breaks/list formatting của tool responses.
2. Cải thiện language behavior:
   - Prompt yêu cầu trả lời cùng ngôn ngữ với message mới nhất.
   - Fake provider có localized deterministic summary hoặc ghi rõ đây là raw evidence mode.
3. Hoàn thiện chat context `UICHAT-05`:
   - UI chọn device và memory context.
4. Chuẩn hóa backend error envelope và cursor pagination (`API-05`, `REPO-04`).

### P1

1. Chạy PDF parser trong subprocess có timeout/resource limits.
2. Usage aggregate/report endpoint và observability outage/redaction tests.
3. Ticket detail/filter và thống nhất frontend query invalidation.
4. OpenAPI → TypeScript contract check và response-model completeness.
5. Retention cleanup jobs và query-plan evidence cho dataset lớn.

### Bằng chứng môi trường còn thiếu

- Live OpenAI text evaluation ba repetitions, cost/variance và human rubric review.
- OpenAI embedding re-index + retrieval baseline với `text-embedding-3-small`.
- Remote GitHub Actions và browser E2E artifacts.
- Full-stack worker/Redis restart drill.
- Clean-machine independent review, demo video và release sign-off.

Danh sách audit đầy đủ ở [plan-gap-audit.md](plan-gap-audit.md).

## 10. Thứ tự đề xuất cho chat mới

1. Chạy `git status --short`; không ghi đè thay đổi chưa rõ nguồn gốc.
2. Chọn đúng một mục P0 nhỏ và đọc `PLAN.md` của module liên quan.
3. Viết regression test trước hoặc cùng implementation.
4. Chạy checks tương ứng; không dùng fake evidence để tuyên bố live quality.
5. Cập nhật PLAN/checklist chỉ khi có implementation và test evidence.
6. Tạo một commit riêng cho lát cắt đó; không push nếu user chưa yêu cầu.

Ưu tiên thực dụng tiếp theo: **SafeMarkdown + localized response behavior + citation excerpt UX**.

## 11. Bản đồ file quan trọng

| Khu vực | File/thư mục |
|---|---|
| Composition/config | `backend/app/main.py`, `backend/app/config.py` |
| LangGraph/RAG flow | `backend/app/agent/graph.py`, `backend/app/agent/rag.py` |
| Fake/OpenAI provider | `backend/app/providers/fake.py`, `backend/app/providers/openai.py` |
| Prompt assets | `backend/app/prompts/` |
| Retrieval/citation | `backend/app/rag/retrieval/`, `backend/app/rag/citations/` |
| Knowledge seed/re-index | `backend/app/demo_document_seed.py`, `backend/app/knowledge_reindex.py` |
| Tools/MCP | `backend/app/tools/`, `backend/app/mcp_server/` |
| Approval/tickets | `backend/app/services/approvals/`, `backend/app/services/tickets/` |
| Jobs/recovery | `backend/app/jobs/` |
| React chat | `frontend/src/features/chat/` |
| API clients | `frontend/src/api/` |
| Migrations | `backend/migrations/versions/` |
| Demo/eval data | `data/`, `evals/` |
| Evidence/reports | `reports/` |

## 12. Nguồn sự thật và quy tắc an toàn

Theo thứ tự ưu tiên khi tài liệu mâu thuẫn:

1. Code + migration + test đang ở Git HEAD.
2. [plan-gap-audit.md](plan-gap-audit.md) cho gap đã đối chiếu.
3. [implementation-roadmap.md](implementation-roadmap.md) cho WP/checklist lịch sử.
4. Các module `PLAN.md` cho yêu cầu chi tiết.

Không làm các việc sau nếu chưa có yêu cầu rõ:

- Không reset/drop database development hoặc xóa named volumes.
- Không chạy paid re-index/live eval.
- Không đưa `.env`, API key hoặc password vào chat/commit/log.
- Không mở PostgreSQL/Redis ra public network.
- Không để model tự cung cấp actor/role/approval state.
- Không đánh dấu release gate pass nếu chưa có artifact/bằng chứng tương ứng.
