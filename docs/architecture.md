# Kiến trúc hệ thống

Trạng thái: kiến trúc V1 đã được triển khai local; production operation và live quality gates còn ngoài phạm vi bằng chứng hiện tại.

## Runtime topology

```mermaid
flowchart TD
    UI["Browser · React"] --> NGINX["Nginx · same-origin /api proxy"]
    NGINX --> API["FastAPI · auth/CSRF/RBAC/API/SSE"]
    API --> SVC["Business services"]
    SVC --> REPO["Scoped repositories"]
    REPO --> PG["PostgreSQL 17 + pgvector"]
    API --> REDIS["Redis · queue/rate limit"]
    BEAT["Celery beat"] --> REDIS
    REDIS --> AW["Agent worker"]
    REDIS --> BW["Background worker"]
    AW --> RUNTIME["Runtime selector"]
    RUNTIME --> SDK["OpenAI Agents SDK · bounded tool loop"]
    RUNTIME --> GRAPH["LangGraph · fake/rollback path"]
    SDK --> CTX["Owner-scoped context service"]
    GRAPH --> CTX
    SDK --> RAG["Hybrid retrieval + citation allowlist"]
    GRAPH --> RAG
    SDK --> EXEC["Governed tool executor + policy"]
    GRAPH --> EXEC
    EXEC --> MCP["MCP stdio subprocess"]
    MCP --> SVC
    SDK --> MODEL["Fake/OpenAI provider + budget ledger"]
    GRAPH --> MODEL
    API -. filtered telemetry .-> OBS["Langfuse/no-op observability"]
    AW -. filtered telemetry .-> OBS
```

Compose có đúng bảy long-running service: frontend, API, agent worker, background worker, scheduler, PostgreSQL và Redis. API/workers dùng cùng production image Python; MCP là subprocess stdio nội bộ, không có public port. Chỉ frontend/API bind vào loopback; datastore nằm trên internal network.

## Ranh giới tin cậy

| Lớp | Trách nhiệm | Ràng buộc |
|---|---|---|
| API/auth | Session cookie, CSRF, actor, owner/role checks, SSE cursor | Không nhận actor/role từ model hoặc request payload |
| Services | State transition, approval, ticket receipt, document/memory lifecycle | Transaction ngắn; không giữ DB transaction qua model call/approval wait |
| Repository/DB | Scoped query, FK/unique/check constraints, durable events | PostgreSQL là nguồn sự thật |
| Agent runtime | Agents SDK tool loop hoặc LangGraph fallback, giới hạn turn/call | Không công khai chain of thought; không ghi ticket trực tiếp |
| Context service | Chọn hội thoại, thiết bị và memory trong owner scope | Không tin actor/context do model cung cấp |
| Tools/MCP | Strict input/output schemas, allowlist, policy, trusted actor/run context | MCP read tools chỉ đọc status và ticket của actor |
| Provider | Structured generation/embedding, token/cost ledger | Không sở hữu side effect; paid call phải qua budget guard |
| Jobs | Queue, lease, heartbeat, retry/reconcile | Redis delivery không được coi exactly-once |
| Frontend | Hiển thị server state, citation, approval và errors | Không tự suy side effect thành công từ model text |

## Ba workflow quan trọng

### Chat/RAG

Message và run được commit trước khi enqueue. Worker claim run rồi dựng owner/device/memory context.
Trong OpenAI mode, Agents SDK tự lặp model → read tool → model với trần cố định; fake mode và đường
rollback dùng LangGraph. Citation cuối chỉ được tạo từ source ID do retrieval của chính run trả về.
SSE reconnect dùng event cursor và không tạo run mới.

### Approval/ticket

Model hoặc form chỉ tạo approval draft. Runtime pause và lưu checkpoint LangGraph hoặc snapshot
Agents SDK; user đúng owner approve/reject trong thời hạn. Resume kiểm tra state, argument hash và
actor. Ticket transaction ghi unique approval receipt nên double-click/retry/crash sau commit vẫn
quy về đúng một ticket.

### Document/memory

PDF upload có MIME/size/path guard, tạo draft version, parse/chunk/embed/store idempotent rồi admin publish. Retrieval/history recheck current version và ACL. Memory extraction luôn hoạt động nhưng chỉ tạo candidate; durable fact vẫn cần user xác nhận. Device scope, optimistic version và epoch ngăn job cũ ghi lại fact sau delete.

## Dữ liệu và durability

- PostgreSQL: identity/session, conversation/run/event, checkpoint, documents/chunks/ACL, approvals/tickets, memory và usage ledger.
- Redis: Celery broker/result plumbing, login rate-limit và lease-related runtime data; AOF `everysec`, `noeviction`.
- Document volume: PDF do ứng dụng quản lý bằng server-owned storage key.
- Backup: PostgreSQL custom dump + document archive + integrity manifest; Redis không nằm trong backup vì durable business state ở PostgreSQL.

## Trade-offs và giới hạn

- Single-company prototype, không có tenant boundary hoàn chỉnh.
- Exact vector scan/full-text phù hợp corpus demo; HNSW/reranker chỉ thêm khi số đo yêu cầu.
- Local files phù hợp demo; production cần object storage, encryption và remote retention.
- Fake provider đảm bảo test deterministic nhưng không đại diện chất lượng model. G-05–G-09 chưa đủ live/human/full-stack evidence.
- Langfuse là observability phụ trợ, không phải audit source of truth.
- Deployment server, TLS, secrets manager, autoscaling và production monitoring chưa thuộc repository này.

Các thay đổi ranh giới nền tảng cần ADR. Runtime nền tảng nằm tại
[ADR-0002](adr/0002-runtime-and-integration.md); quyết định Agents SDK và resumable approval nằm tại
[ADR-0003](adr/0003-openai-agents-orchestrator.md); hướng vận hành ở
[infra commands](../infra/commands.md).
