# Kiến trúc Memory & Context Management cho IT Support Agent

Trạng thái: **đề xuất kiến trúc, chưa triển khai**  
Ngày đánh giá code: **2026-10-07**  
Phạm vi: backend agent, context, memory, RAG, tool, persistence, security và evaluation.  

> Quy ước bằng chứng
>
> - **Observed from code**: có thể truy vết tới file, class, function hoặc migration trong repository.
> - **Architectural proposal**: thiết kế đích; component chưa tồn tại cho tới khi phase tương ứng được triển khai.
> - **Architectural assumption**: giả định cần được product/security xác nhận trước khi triển khai.

---

## 1. Executive Summary

Repository hiện tại đã có nền móng tốt để phát triển memory có kiểm soát: PostgreSQL là nguồn sự thật, run có lease và state transition, tool có allowlist/RBAC/approval, RAG có ACL và document versioning, hội thoại được giới hạn token, và fact cá nhân chỉ trở thành memory sau khi người dùng xác nhận. Vì vậy không nên thay runtime hay đưa thêm một database mới ở MVP.

Khoảng trống lớn nhất nằm ở giữa runtime và các nguồn dữ liệu. `SupportAgentState` chỉ sống trong một lượt LangGraph; Agents SDK chỉ lưu snapshot khi chờ approval; `Conversation.issue_state` chưa có contract; và `build_agent_context()` mới chọn history theo recency/token. Hệ thống chưa có một **Working Memory bền vững**, chưa có **Context Manager dùng chung trước mọi LLM call**, chưa biến ticket/tool trajectory thành **Episodic Memory**, và chưa có **Procedural Memory** được version, phê duyệt và theo dõi hiệu quả.

Kiến trúc đề xuất giữ hai runtime hiện có nhưng đặt một lớp hợp đồng dùng chung quanh chúng:

1. `WorkingMemoryService` lưu task state có version cho từng run/incident.
2. `ContextManager` dựng `ActiveContext` từ request, working memory, history, semantic/episodic/procedural memory, RAG và tool observations theo budget và trust.
3. `MemoryService` quản lý semantic và episodic memory với provenance, temporal validity, conflict và owner/tenant scope.
4. `ProcedureService` lưu procedure dưới dạng workflow đã phê duyệt; procedure không cấp quyền thực thi.
5. `MemoryLifecycleManager` dùng policy deterministic trước, model chỉ đề xuất; mọi mutation nhạy cảm có validation/audit/human gate.
6. PostgreSQL + pgvector tiếp tục là storage mặc định. Redis chỉ làm queue/cache; không là nguồn sự thật.

MVP nên đi theo bốn lát cắt: (1) durable working memory + unified context manager, (2) semantic/episodic memory, (3) lifecycle/conflict/audit, (4) procedural memory có approval. RL từ AgeMem, MemAct và Memory-R1, learned fusion, graph database và multi-agent shared memory được giữ ở future research cho tới khi benchmark chứng minh nhu cầu.

---

## 2. Phân tích kiến trúc repository hiện tại

### 2.1 Sơ đồ hiện tại

**Observed from code**

```mermaid
flowchart LR
    U[React UI] -->|HTTP + SSE| API[FastAPI]
    API -->|commit Message + AgentRun| PG[(PostgreSQL 17 + pgvector)]
    API -->|enqueue| R[(Redis)]
    R --> AW[Celery agent worker]
    R --> BW[Celery background worker]
    AW --> SC[SupportContextService]
    SC --> H[Messages]
    SC --> MF[Confirmed MemoryFacts]
    SC --> D[UserDevice]
    AW --> RS{Runtime selector}
    RS -->|OpenAI/auto| SDK[OpenAI Agents SDK]
    RS -->|fake/rollback| LG[LangGraph]
    SDK --> TE[ToolExecutor]
    LG --> TE
    TE --> KR[Local Knowledge Search]
    TE --> MCP[MCP stdio read tools]
    KR --> RAG[Hybrid retrieval]
    RAG --> PG
    MCP --> PG
    SDK --> OA[OpenAI Responses]
    LG --> PR[Structured provider]
    AW -->|events, answer, citations| PG
    BW -->|memory extraction candidates| PG
    SDK -. filtered trace .-> LF[Langfuse optional]
```

### 2.2 Component inventory

| Component | Bằng chứng code | Vai trò và data flow | Điểm mạnh | Hạn chế / tái sử dụng |
|---|---|---|---|---|
| API composition | `backend/app/main.py::create_app` | Gắn auth, conversation, run, document, memory, source, ticket routers; tạo DB/Redis/provider/observer | Dependency lifecycle rõ | Không phải orchestration layer; giữ nguyên |
| Durable run | `db/models.py::AgentRun`, `RunEvent`; `services/conversations/run_state.py`, `run_lease.py` | Message/run commit trước enqueue; worker claim lease; event có sequence/dedupe | Recovery, idempotency và một active run/conversation | Counters/event không thay thế task state có schema |
| Runtime selector | `jobs/worker.py::execute_agent_run` | OpenAI Agents SDK cho OpenAI/auto; LangGraph cho fake/rollback | Có đường rollback | Hai runtime có cách dựng loop/state khác nhau; cần contract context chung |
| Dynamic agent loop | `agent/openai_agents_runtime.py::OpenAIAgentsRuntime` | `Runner.run_streamed`, tối đa sáu turn, tool choice auto, không parallel tool | Model có thể chọn chuỗi read tool theo observation | Snapshot chỉ lưu khi approval; active context chỉ dựng một lần đầu run |
| Bounded graph | `agent/graph.py::build_support_graph`; `agent/state.py::SupportAgentState` | Graph load/decide/tool/RAG/generate/validate; model/retrieval limit | Deterministic, testable | Topology do app nối sẵn; production graph compile không gắn checkpointer chung cho working state |
| Provider abstraction | `providers/base.py::StructuredResponseProvider`; `providers/openai.py` | Query analysis, planning, tool choice, structured reply, embedding | Contract Pydantic, usage ledger, citations validated | Các prompt/context paths chưa hội tụ hoàn toàn |
| Request policy | `agent/request_policy.py`; `rag/retrieval/analysis.py` | Phân tích latest query, giữ exact terms, route knowledge/tool | Giảm topic leakage; deterministic-first | Đây là intent/tool safety policy, không nên trở thành memory/context manager |
| Context loader | `agent/context/service.py::SupportContextService` | Owner-scoped conversation/device, 120 recent messages, authorized history, confirmed facts | Authorization trước context | Chưa load task state, episodes, procedures; limit cố định |
| Context builder | `agent/context/builder.py::build_agent_context` | Giữ current query cuối; summarize history cũ; chọn recency dưới 10k token | Có budget, truncate, phân biệt assistant suggestion với user-confirmed attempt | Token estimate thô; không score relevance/trust/validity/cost; chỉ history + semantic facts |
| Conversation summary | `agent/context/summary.py::summarize_conversation` | Extractive summary từ tối đa tám message cũ | Rẻ, deterministic, gắn nhãn untrusted | Không có goal/plan/observation structured; có thể làm mất dependency |
| Semantic memory MVP | `memory/lifecycle.py`, `memory/retrieval.py`, `memory/extractor.py`; migrations 0014/0015/0018 | User message → async job → candidate → user confirm → fact 90 ngày → max 5 facts vào context | Owner/device FK, epoch chống stale job, soft delete, optimistic version, explicit confirmation | Chỉ profile/preference/device allowlist; regex extraction; không relevance, confidence, conflict record, source authority |
| Knowledge/RAG | `rag/ingestion/*`, `rag/retrieval/*`, `rag/citations/sources.py` | Parse/chunk/embed; dense + BM25/FTS + exact; fusion/rerank/diversity/expansion; evidence selection | ACL/current version/effective dates, citation allowlist, provenance offsets | Knowledge tốt nhưng không phải memory; chưa truy hồi episode/procedure |
| Tool boundary | `tools/registry.py`, `executor.py`, `policy.py`; `mcp_server/*` | Validate schema → role/policy → local search hoặc stdio MCP; create ticket luôn approval | Actor/run/role do server cung cấp; timeout, output limit, duplicate call guard | Tool result chưa có durable normalized observation/verification schema |
| Approval | `ApprovalRequest`; `services/approvals/*`; `AgentRuntimeState` | Hash immutable args, owner decision, pause/resume, idempotent ticket receipt | Ranh giới side effect đúng | Runtime snapshot là approval checkpoint, không phải working memory chung |
| IT records | `User`, `UserDevice`, `Ticket`, `TicketEvent`, `ServiceState`, `Conversation`, `Message` | Identity/device/ticket/service/current dialogue | Có owner/department scope, ticket events | Không có CMDB/asset/incident entity đầy đủ; `UserDevice` là inventory tối giản |
| Jobs/infra | `jobs/*`, `infra/compose.yaml` | Celery agent/background/beat qua Redis; durable data ở PostgreSQL | Queue tách loại workload, lease/reconcile | Không có DLQ/production SLO evidence trong repository |
| Observability | `observability.py`, diagnostics/logging, usage ledger, run events | Optional Langfuse + safe operational events/cost | Sensitive trace disabled in SDK | Chưa có memory/context-specific metrics và audit lineage hoàn chỉnh |
| Testing | 86 test files: unit, integration, contract | Runtime, RAG, auth, approval, memory, recovery | Coverage theo boundary khá rộng | Chưa có long-horizon memory benchmark, interruption/resume task benchmark, poisoning suite |

### 2.3 Dữ liệu IT Support hiện có

**Observed from code**

- `User` và `Department`: identity, role, department, active state.
- `UserDevice`: owner, label, platform, active/version. Đây chưa phải CMDB asset vì thiếu serial, ownership authority, installed software, posture và sync source.
- `Conversation`/`Message`: history; `issue_state` là JSONB nhưng không có typed contract hoặc service cập nhật nhất quán.
- `AgentRun`/`RunEvent`: execution envelope và safe event stream.
- `Ticket`/`TicketEvent`: issue type/severity/status/resolution và event history; đây là nguồn tốt nhất để xây episode sau này.
- `ApprovalRequest`: proposed side effect, immutable argument hash, decision/execution times.
- `ServiceState`: allowlisted simulated service health.
- Không tìm thấy model riêng cho `Incident`, `Asset/CMDB record`, normalized `ToolExecution`, `TroubleshootingAttempt`, `WorkingMemory` hoặc `Procedure`.

### 2.4 Infrastructure hiện tại

**Observed from code**

- Python 3.12, FastAPI, Pydantic, SQLAlchemy async.
- OpenAI Python client, OpenAI Agents SDK và LangGraph.
- PostgreSQL 17 + pgvector; `TSVECTOR` cho sparse search; BM25s trong process là lựa chọn sparse khác.
- Redis 7 cho Celery và rate limiting; Celery agent/background workers + beat.
- Session cookie, CSRF, RBAC/owner checks; document ACL theo visibility/department/IT.
- Python logging với safe fields, request ID, optional Langfuse, usage ledger.
- Pytest unit/integration/contract; Ruff và mypy cấu hình trong `backend/pyproject.toml`.

**Architectural assumption cần xác nhận**: sản phẩm hiện là single-company prototype. Nếu triển khai SaaS/multi-tenant, mọi bảng memory/context mới phải có `tenant_id`; không thể chỉ dựa vào `owner_id` và `department_id`.

---

## 3. Agent Runtime hiện tại

### 3.1 OpenAI Agents SDK path

**Observed from code**

1. Worker load current user message và dựng `Principal` từ DB.
2. `SupportContextService` load authorized history, confirmed facts và active device.
3. `resolve_request_policy()` phân tích duy nhất request mới.
4. Worker tạo retriever, knowledge search, tool executor và `SupportSDKContext`.
5. `build_agents_input()` gọi `build_agent_context()`, đưa summary/history/memory thành message riêng và current query ở cuối.
6. `Runner.run_streamed()` cho model chọn tool kế tiếp, tối đa sáu model turn và bốn read tool calls.
7. Tool call phải qua request relevance policy và `ToolExecutor`.
8. Final output theo schema, citations phải thuộc citation store của run; guardrail kiểm tra yêu cầu knowledge/retrieval.
9. Nếu `create_ticket`, runtime pause, lưu serialized SDK state, chờ owner approve/reject rồi worker khác có thể resume.

Đây là một agent loop thực sự theo nghĩa **model → action/tool → observation → model**. Nó không công khai chain-of-thought; progress chỉ là stage an toàn. Planning nội bộ của model không đồng nghĩa với một kế hoạch durable và có thể inspect/resume.

### 3.2 LangGraph path

**Observed from code**

Graph hiện có topology ứng dụng định nghĩa:

```text
START → load_context → decide_action
  ├─ direct → generate → validate → END/retry/no_answer
  ├─ read tool → execute_tool → respond_tool → END
  └─ knowledge → rewrite → retrieve → decide_evidence
                                  ├─ generate → validate
                                  └─ no_answer → END
```

`SupportAgentState` chứa query/history/evidence/answer/counters và một số planning metadata. `run_support_graph()` giới hạn bốn model call, bốn retrieval call và recursion 24. Migration có LangGraph checkpoint tables và approval checkpoint spike, nhưng graph support chính gọi `builder.compile()` không truyền checkpointer. Vì vậy không được xem graph state hiện tại là durable working memory cho troubleshooting dài.

### 3.3 Tool permissions và lifecycle

**Observed from code**

- Registry là allowlist duy nhất; arguments/output dùng Pydantic.
- `ToolPolicyEngine` quyết định allow/approval/deny từ server-known role và tool policy.
- `search_knowledge_base` chạy local; profile/service/ticket reads chạy MCP stdio; create-ticket là approval route.
- Actor ID, role, database URL và run ID do worker cung cấp; model không được tự khai actor.
- Timeout, max result bytes, duplicate arguments và output validation được enforce.
- Approval không giữ DB transaction qua thời gian chờ; argument hash, optimistic version, expiry và idempotent ticket write giảm replay/double-submit.

### 3.4 Multi-agent

**Observed from code**: không có handoff, specialist agent registry, shared blackboard hoặc agent namespace. Tên `IT Support Orchestrator` là một agent duy nhất. Thiết kế mới phải giữ single-agent ở MVP và chỉ chuẩn bị namespace/ownership cho tương lai.

---

## 4. Memory/Context hiện tại

### 4.1 Năm khái niệm phải tách

| Khái niệm | Hiện trạng |
|---|---|
| Active LLM Context | Có: message list do `build_agents_input()` dựng; graph provider cũng dùng bounded history/evidence |
| Working/Short-Term Memory | Một phần: state trong run và `Conversation.issue_state`, nhưng chưa có durable typed service |
| Long-Term Semantic Memory | Có MVP: confirmed profile/preference/device facts, TTL 90 ngày |
| Long-Term Episodic Memory | Chưa có; raw ticket/event/message tồn tại nhưng chưa được consolidate/retrieve như episode |
| Procedural Memory | Chưa có; official runbook nằm trong Knowledge Base |
| Knowledge Base | Có và khá hoàn chỉnh: document/version/chunk/ACL/hybrid retrieval/citation |

### 4.2 History được đưa vào model như thế nào

**Observed from code**

`SupportContextService` lấy tối đa 120 message gần nhất, loại current message và lọc citation/document authorization. Confirmed facts được thêm dưới role logic `memory`. `build_agent_context()`:

- luôn giữ request hiện tại;
- ước lượng token bằng byte UTF-8 chia ba;
- summarize khi history trên 20 messages hoặc khoảng 6.000 token;
- giữ 12 dialogue gần nhất sau summary;
- lấy item từ mới về cũ trong tổng budget 10.000;
- giữ assistant steps ở lane “suggested”, chỉ coi là attempted nếu user nói rõ đã thử;
- Agents SDK chuyển summary/memory thành user messages có XML-like `context_only` tags và đặt current request ở user turn cuối.

### 4.3 Persistent memory lifecycle hiện tại

**Observed from code**

```mermaid
flowchart LR
    UM[Owned user message] --> J[Extraction job]
    J -->|regex allowlist| C[Pending candidate · TTL 7d]
    C -->|confirm/edit| F[MemoryFact · TTL 90d]
    C -->|reject/expire| X[Closed candidate]
    F -->|edit/delete| E[Increment memory_epoch]
    E -->|stale extraction| S[Discard stale job]
    F -->|owner + optional device scope; max 5| AC[Agent context]
```

Điểm bảo vệ đáng giữ: source phải là owned user message; candidate chưa được tự dùng; device composite FK chống cross-owner; stale job bị chặn bằng epoch; update/delete có optimistic version.

---

## 5. Các vấn đề hiện tại

| Capability | Hiện tại | Vấn đề | Paper liên quan | Đề xuất |
|---|---|---|---|---|
| Working Memory | Turn state + run + untyped `issue_state` | Không có durable goal/plan/hypothesis/verification; khó resume sau crash/approval | AgeMem, MemAct, MemGPT | Typed `WorkingMemorySnapshot` versioned theo run |
| Context Management | Recency + threshold summary + token cap | Không hợp nhất tool observations/RAG/procedure; không score trust/utility/conflict | MemAct, MemGPT | `ContextManager` chung cho từng LLM call |
| Semantic LTM | 3 kind, user-confirmed, max 5 recent | Không relevance/confidence/provenance authority/temporal conflict | Mem0, A-MEM, Memory-R1 | Typed facts + sources + assertions/conflicts |
| Episodic LTM | Raw tickets/messages/events | Chưa consolidate, retrieve hoặc liên kết outcome | Mem0, A-MEM | Episode từ completed run/resolved ticket |
| Memory Lifecycle | Candidate confirm/update/delete/expiry | Chưa có generalized ADD/UPDATE/DELETE/NOOP decision record | Memory-R1 | Deterministic policy + model proposal + validator |
| Procedural Memory | Official runbook trong KB | Không học/reuse successful trajectories; không success/failure metrics | Memp | Versioned, human-approved procedure registry |
| Knowledge Retrieval | Hybrid, ACL, rerank, citation | Chưa phối hợp budget với other context sources | RAG/MemGPT | Giữ retriever; context manager chọn evidence |
| Recovery | Run lease; approval snapshot | Không resume giữa chuỗi diagnostic tools từ typed state | MemAct/MemGPT | Persist observation + state atomically per step |
| Security | Owner scope, role, approvals, doc ACL | Chưa tenant/team/agent scopes; chưa memory poisoning audit | Enterprise requirement | ABAC envelope + provenance + quarantine + audit |
| IT Agent Evaluation | Retrieval benchmark và tests | Thiếu long-horizon/tool/task/memory benchmark | ITBench | Scenario sandbox + state/outcome evaluators |

Các lỗi kiến trúc nổi bật:

1. **State và context bị trộn ý nghĩa.** Có dữ liệu trong prompt không có nghĩa nó đã được persist; có dữ liệu trong DB không có nghĩa nó nên vào prompt.
2. **Context chỉ dựng đầu run trong SDK.** Sau 20–30 tool call giả định trong tương lai, runtime phụ thuộc vào SDK transcript; app chưa chủ động compact từng observation.
3. **Memory retrieval theo recency.** Năm fact mới nhất có thể không liên quan request, trong khi fact cũ nhưng quan trọng bị loại.
4. **Không có trust hierarchy.** User-confirmed fact tốt hơn raw extraction, nhưng CMDB/IdP/MDM authoritative chưa được model hóa để thắng conflict.
5. **Ticket không tự động là episode.** Raw ticket có thể thiếu cause/verification; cần consolidation sau resolution.
6. **Procedure và permission chưa có ranh giới dữ liệu.** Prompt đã nói memory không cấp quyền, nhưng schema procedure tương lai phải thể hiện required permissions/approval độc lập.
7. **Hai runtime có nguy cơ drift.** Mỗi runtime tự map history/evidence/tool loop; context policy mới phải là provider/runtime neutral.

---

## 6. Research-to-Architecture Mapping

### 6.1 Tổng hợp quyết định

| Nguồn | Contribution chính | Quyết định | Phần dùng cho dự án |
|---|---|---|---|
| [AgeMem, ACL 2026](https://aclanthology.org/2026.acl-long.981/) | Unified LTM/STM operations trong policy; ADD/UPDATE/DELETE/RETRIEVE/SUMMARY/FILTER; progressive RL | **ADAPT** primitive; **FUTURE** RL | Cùng vocabulary lifecycle/context action, budgets và action telemetry |
| [MemAct, ACL Findings 2026](https://aclanthology.org/2026.findings-acl.956/) | Prune&Write theo ID để curate working context; DCPO cho RL | **ADAPT** | Addressable observations + deterministic KEEP/DROP/SUMMARIZE; model chỉ đề xuất |
| [MemGPT, 2023](https://arxiv.org/abs/2310.08560) | Memory hierarchy, queue pressure, paging, recall/archival storage, function chaining | **ADOPT** hierarchy; **ADAPT** self-management | Active context ≠ external memory; pressure thresholds; paginated retrieval |
| [Mem0, 2025](https://arxiv.org/abs/2504.19413) | Async summary + recent window; extract then compare top similar memories; ADD/UPDATE/DELETE/NOOP | **ADOPT/ADAPT** | Async candidate extraction, similar-memory comparison, explicit operations |
| [A-MEM, NeurIPS 2025](https://arxiv.org/abs/2502.12110) | Atomic structured notes, embeddings, semantic links, memory evolution | **ADAPT** | Typed incident links in relational tables; immutable source + derived annotations |
| [Memory-R1, ACL 2026](https://aclanthology.org/2026.acl-long.583/) | RL-trained manager and answer agent; operation selection and memory distillation | **ADOPT** operation contract; **FUTURE** RL | Auditable decision records and retrieval distillation; rule/model hybrid MVP |
| [Memp, ACL Findings 2026](https://arxiv.org/abs/2508.06433) | Trajectory + script proceduralization; retrieval; validation/adjustment/deprecation | **ADAPT** | Procedure candidates from successful verified trajectories, human approval/versioning |
| [ITBench, ICML 2025](https://proceedings.mlr.press/v267/jha25a.html) | 102 realistic SRE/CISO/FinOps scenarios; task success and interpretable metrics | **ADAPT** | Isolated executable IT support scenarios, outcome/state/side-effect scoring |

### 6.2 Đánh giá từng paper theo 11 câu hỏi

#### AgeMem

1. **Vấn đề**: LTM và STM thường được quản lý rời rạc bằng heuristic, làm giảm hiệu quả long-horizon.
2. **Kiến trúc**: một policy quan sát context, LTM và task; language generation và memory operations ở cùng action space.
3. **Algorithm**: sáu tool operation; huấn luyện ba stage (LTM construction, STM dưới distractor, phối hợp); step-wise GRPO truyền terminal reward về memory decisions.
4. **Representation**: LTM store và STM/context; paper tập trung policy operation hơn enterprise schema/provenance.
5. **Retrieval**: `RETRIEVE` top-k semantic từ LTM vào context.
6. **Update**: LTM ADD/UPDATE/DELETE; STM SUMMARY/FILTER.
7. **Training**: có cho kết quả chính.
8. **RL**: có, là contribution trung tâm.
9. **Chi phí**: cao; cần trajectories, rollouts, reward, model train/serve và governance.
10. **Điểm yếu**: reward/task distribution có thể không phản ánh security/authority; learned deletion khó audit; benchmark khác IT operations.
11. **Phù hợp**: vocabulary thống nhất và telemetry rất phù hợp; end-to-end RL chưa phù hợp MVP. **ADAPT**, RL là **FUTURE**.

#### MemAct

1. **Vấn đề**: context dài gây attention dilution; external/static compaction không hiểu reasoning state.
2. **Kiến trúc**: working memory là sequence record có ID; policy có task action và memory action.
3. **Algorithm**: `Prune&Write(target_ids, content)` xóa record đã chỉ định và chèn summary/reflection/plan; DCPO chia trajectory tại edit point để train đúng context.
4. **Representation**: record `(action, observation, id)` và memory note in-place.
5. **Retrieval**: chủ yếu active working context curation, không phải LTM retriever hoàn chỉnh.
6. **Update**: prune chọn lọc + append memory record có thể tiếp tục được address.
7. **Training**: SFT rồi RL cho kết quả paper.
8. **RL**: có trong DCPO; paper ghi nhận frontier model cũng khó tự dùng memory tool ổn định nếu không train.
9. **Chi phí**: cao khi train; inference giảm token nhưng thêm memory actions.
10. **Điểm yếu**: có thể xóa chi tiết chỉ quan trọng về sau; summary do model có thể sai; credit assignment phức tạp.
11. **Phù hợp**: ID ổn định cho tool observations và compaction rất hữu ích. Dùng deterministic retention + model summary có provenance. **ADAPT**; DCPO **FUTURE**.

#### MemGPT

1. **Vấn đề**: finite context trong multi-session chat và document analysis.
2. **Kiến trúc**: main context gồm system instructions, read/write working block, FIFO queue; external context gồm recall và archival storage; queue manager + function executor.
3. **Algorithm**: warning threshold, flush threshold, recursive summary, paging/search, heartbeat để chain functions.
4. **Representation**: prompt tiers và external text records; recall giữ message đầy đủ.
5. **Retrieval**: agent-invoked paginated search; example dùng embedding cosine/PostgreSQL pgvector/HNSW.
6. **Update**: function calls tự edit working context và archival memory.
7. **Training**: không bắt buộc; dựa prompt/function calling.
8. **RL**: không.
9. **Chi phí**: trung bình; thêm storage/search và nhiều inference khi paging.
10. **Điểm yếu**: phụ thuộc model gọi function tốt; self-edit có thể sai; recursive summary mất thông tin; thiết kế gốc không đủ enterprise provenance/RBAC.
11. **Phù hợp**: hierarchy, memory pressure, paging và function chaining. **ADOPT** concept, **ADAPT** control sang server policy.

#### Mem0

1. **Vấn đề**: coherent cross-session memory với chi phí thấp hơn full context.
2. **Kiến trúc**: incremental two-phase extraction/update; graph variant biểu diễn entity/relation.
3. **Algorithm**: async conversation summary + recent messages + new exchange → extracted facts; top-s similar memories → LLM chọn ADD/UPDATE/DELETE/NOOP.
4. **Representation**: dense natural-language memories; graph variant là directed labeled graph.
5. **Retrieval**: vector similarity; graph variant bổ sung entity/relation traversal.
6. **Update**: compare candidate với memories gần nhất và execute một trong bốn operation.
7. **Training**: không bắt buộc; paper dùng inference model.
8. **RL**: không.
9. **Chi phí**: trung bình; extraction/update LLM calls + embedding/store. Paper báo latency/token thấp hơn full context, nhưng không nên chuyển số đó trực tiếp sang workload này.
10. **Điểm yếu**: LLM mutation có thể xóa/update sai; graph chỉ cải thiện nhỏ và có case kém base; benchmark hội thoại không đo authorization.
11. **Phù hợp**: pipeline async, compare-before-write và operation contract. **ADOPT** pipeline, **ADAPT** bằng human/authority gates; graph **FUTURE**.

#### A-MEM

1. **Vấn đề**: flat memory thiếu cấu trúc và khó tiến hóa khi experience tăng.
2. **Kiến trúc**: Zettelkasten-inspired atomic notes; note construction, link generation, memory evolution, retrieval.
3. **Algorithm**: LLM sinh keyword/tag/context; embed; top-k neighbors; LLM tạo links và cập nhật metadata của notes liên quan.
4. **Representation**: `{content, timestamp, keywords, tags, contextual_description, embedding, links}`.
5. **Retrieval**: cosine top-k; linked memories có thể được mở rộng cùng “box”.
6. **Update**: new note có thể làm evolve context/keyword/tag của existing notes.
7. **Training**: không bắt buộc.
8. **RL**: không.
9. **Chi phí**: trung bình đến cao vì nhiều LLM calls/link maintenance.
10. **Điểm yếu**: generated links/metadata có thể drift; replacing evolved notes làm yếu provenance; top-k lớn tăng token; chưa có enterprise authority.
11. **Phù hợp**: atomic episodes và typed links. Không cho model overwrite source; lưu derived annotation/version riêng. **ADAPT**; graph DB **REJECT cho MVP**.

#### Memory-R1

1. **Vấn đề**: heuristic memory manager và static retrieval không tối ưu theo downstream answer.
2. **Kiến trúc**: Memory Manager xây/evolve bank; Answer Agent distill 60 retrieved candidates rồi answer.
3. **Algorithm**: manager chọn ADD/UPDATE/DELETE/NOOP; manager và answer agent fine-tune PPO/GRPO với outcome reward.
4. **Representation**: temporal natural-language memory entries có ID.
5. **Retrieval**: similarity RAG lấy candidates; Answer Agent chọn/distill relevant entries.
6. **Update**: operation + updated content do manager tạo.
7. **Training**: có cho contribution chính.
8. **RL**: có, PPO hoặc GRPO.
9. **Chi phí**: cao cho data/reward/training/two-agent serving; inference có thêm manager/distillation.
10. **Điểm yếu**: exact-match reward có thể ưu tiên answer hơn factual/audit safety; dữ liệu hội thoại nhỏ; learned delete rủi ro.
11. **Phù hợp**: operation schema và outcome-based offline evaluation. MVP dùng rules + LLM proposal + validator, không train RL. **ADAPT**, RL **FUTURE**.

#### Memp

1. **Vấn đề**: procedure thường hard-code hoặc nằm trong weights, khó update và reuse.
2. **Kiến trúc**: repository xây từ trajectories dưới dạng raw trajectory, abstract script hoặc kết hợp; retrieve và online update.
3. **Algorithm**: proceduralization; vector retrieval bằng query/feature keys; update vanilla, validation hoặc adjustment.
4. **Representation**: fine-grained trajectory + high-level script.
5. **Retrieval**: cosine similarity theo query hoặc average task factors; top-k, quá nhiều memory có thể làm giảm hiệu năng.
6. **Update**: append; chỉ consolidate success; failed execution có thể revise procedure; deprecate obsolete entries.
7. **Training**: không nhất thiết train weights; cần model distill trajectories.
8. **RL**: không bắt buộc; dùng benchmark reward/feedback.
9. **Chi phí**: trung bình; storage, embeddings, offline distillation, validation/human review.
10. **Điểm yếu**: success không chứng minh an toàn/causal correctness; benchmark travel/household khác enterprise IT; procedure contamination.
11. **Phù hợp**: dual representation, success/failure tracking, correction/deprecation. Chỉ publish sau verification + human approval. **ADAPT**.

#### ITBench

1. **Vấn đề**: thiếu benchmark thực tế, reproducible và interpretable cho IT automation agents.
2. **Kiến trúc**: framework scenario-based với environments/workloads, agent interface, validators và metrics cho SRE/CISO/FinOps.
3. **Algorithm**: chạy scenario trong environment, thu trajectory/artifacts, chấm trạng thái cuối và task-specific outcomes.
4. **Representation**: không phải memory paper; task/scenario, environment state, tools và evaluators.
5. **Retrieval**: không phải contribution chính.
6. **Update**: không quản lý memory.
7. **Training**: không bắt buộc để dùng benchmark.
8. **RL**: không.
9. **Chi phí**: trung bình đến cao vì cần sandbox, fixtures, reset và evaluators đáng tin cậy.
10. **Điểm yếu**: domain SRE/CISO/FinOps rộng hơn helpdesk; không đo trực tiếp consent/conflict/delete memory.
11. **Phù hợp**: cấu trúc executable scenario và task success. Adapt thành VPN/GitLab/registry/account/ticket scenarios. **ADAPT**.

---

## 7. Memory Taxonomy

| Tầng | Nội dung | Thời gian sống | Source of truth | Có trực tiếp vào prompt? |
|---|---|---:|---|---|
| Active LLM Context | Bundle đã chọn cho đúng một model call | Một call | `ContextManager` build artifact | Có |
| Working Memory | Goal, plan, state, observations, hypothesis, pending approval/verification | Một run/incident; có thể resume | PostgreSQL snapshot + append-only events | Chỉ phần được chọn |
| Semantic Memory | User/device preferences và facts tương đối ổn định | Ngày–tháng hoặc theo source validity | Authoritative system hoặc confirmed fact | Khi relevant và allowed |
| Episodic Memory | Incident/ticket/trajectory/resolution/outcome cụ thể | Theo retention policy | Consolidated record liên kết immutable events | Khi cùng user/device/error/task |
| Procedural Memory | Workflow tổng quát và verified examples | Versioned cho tới deprecate | Approved procedure registry | Khi task/constraints match |
| Knowledge Base | Documentation, FAQ, policy, official runbook | Theo document version/effective dates | Published document version | Evidence chunks có citation |

Quy tắc: Knowledge trả lời “tổ chức quy định gì”; semantic memory trả lời “đối tượng này có thuộc tính gì”; episode trả lời “đã từng xảy ra gì”; procedure trả lời “workflow đã được kiểm chứng là gì”; working memory trả lời “task hiện tại đang ở đâu”; active context chỉ là view tạm thời của các nguồn đó.

---

## 8. Proposed Architecture

**Architectural proposal**

```mermaid
flowchart TB
    REQ[Current request] --> AR[Agent Runtime Adapter]
    AR --> ORCH[Plan → Act → Observe → Verify]
    ORCH <--> WM[WorkingMemoryService]
    ORCH --> CM[ContextManager]
    CM --> HP[Hard policy filters]
    HP --> CS[Context scoring + conflict resolver]
    CS --> TB[Token budget + dedupe + compression]
    TB --> AC[ActiveContext for one LLM call]
    AC --> LLM[LLM]
    LLM --> ORCH

    CM --> HR[Relevant conversation history]
    CM --> SM[Semantic Memory]
    CM --> EM[Episodic Memory]
    CM --> PM[Procedural Memory]
    CM --> KB[Knowledge/RAG]
    CM --> OBS[Tool observations]

    ORCH --> TP[ToolPolicy + authorization]
    TP -->|read| TOOLS[Tool/MCP services]
    TP -->|sensitive| APR[Approval]
    TOOLS --> OBS
    APR --> TOOLS

    WM --> ML[MemoryLifecycleManager]
    OBS --> ML
    ML --> CAND[Quarantined candidates]
    CAND -->|validate/confirm| SM
    CAND -->|resolution verified| EM
    EM -->|offline distill + human approve| PM

    SM --> PG[(PostgreSQL + pgvector)]
    EM --> PG
    PM --> PG
    WM --> PG
    KB --> PG
    ML --> AUDIT[Append-only memory audit]
```

### 8.1 Design principles

1. **Database state before model state**: durable truth nằm trong typed records; model context là projection.
2. **Server policy before model choice**: model có thể đề xuất KEEP/DROP/SUMMARIZE hoặc memory operation; server enforce scope, retention, authority và approval.
3. **Immutable evidence, versioned derivation**: source message/tool result/ticket event không bị model rewrite; summary/fact/procedure tạo version mới và trỏ provenance.
4. **Latest request remains dominant**: history/memory chỉ giải quyết reference hoặc cung cấp evidence liên quan.
5. **Authority is not similarity**: source authoritative thắng conflict dù vector score thấp hơn.
6. **Memory never authorizes**: tool authorization luôn dựa principal/policy/live system state.
7. **One contract, two adapters**: Agents SDK và LangGraph đều gọi cùng Working Memory, Context Manager, Memory/Procedure/RAG services.
8. **Measure before learning**: rules và transparent scoring trước; learned policy/RL chỉ khi ablation chứng minh giá trị.

---

## 9. Working Memory Design

### 9.1 State schema

**Architectural proposal**

```yaml
WorkingMemorySnapshot:
  id: uuid
  tenant_id: uuid | null       # bắt buộc nếu sản phẩm thành multi-tenant
  run_id: uuid
  conversation_id: uuid
  owner_id: uuid
  ticket_id: uuid | null
  incident_key: string | null
  status: active | waiting_input | waiting_approval | verifying | completed | failed | cancelled
  goal:
    statement: string
    success_criteria: [string]
    constraints: [string]
  entities:
    user_id: uuid
    device_id: uuid | null
    service_ids: [string]
  plan:
    version: integer
    steps:
      - id: string
        title: string
        kind: inspect | retrieve | diagnose | action | verify | communicate
        status: pending | running | succeeded | failed | skipped | blocked
        depends_on: [string]
        tool_name: string | null
        requires_approval: boolean
  hypotheses:
    - id: string
      statement: string
      confidence: number
      status: active | supported | rejected
      evidence_refs: [string]
  observations:
    - id: string
      source_type: user | tool | knowledge | system
      source_ref: string
      summary: string
      raw_artifact_ref: string | null
      observed_at: datetime
      reliability: number
      supersedes: string | null
  pending_actions: [string]
  verification_requirements: [string]
  context_compaction:
    last_compacted_event_sequence: integer
    summary_version: integer
    summary: string | null
  counters:
    model_calls: integer
    tool_calls: integer
    retrieval_calls: integer
  schema_version: integer
  version: integer
  created_at: datetime
  updated_at: datetime
```

Không lưu hidden chain-of-thought. `hypotheses` là kết luận vận hành ngắn có evidence refs; `plan` là observable action plan; `observations` là facts từ tool/user/system. Raw payload lớn nằm ở artifact/event storage, snapshot chỉ giữ reference + bounded summary.

### 9.2 State transitions

```mermaid
stateDiagram-v2
    [*] --> Active
    Active --> WaitingInput: thiếu dữ liệu cần thiết
    WaitingInput --> Active: user bổ sung
    Active --> WaitingApproval: action nhạy cảm
    WaitingApproval --> Active: approved/rejected + resume
    Active --> Verifying: action đã thực hiện
    Verifying --> Active: verification failed, replan
    Verifying --> Completed: success criteria đạt
    Active --> Failed: budget/retry/nonrecoverable failure
    Active --> Cancelled: owner/system cancel
    WaitingInput --> Cancelled
    WaitingApproval --> Cancelled
```

Mỗi transition ghi một `WorkingMemoryEvent` append-only và tạo snapshot mới trong cùng transaction. Update dùng `WHERE version = expected_version`; một run chỉ có một lease owner như cơ chế hiện tại. Snapshot giúp read nhanh, event stream phục vụ audit/rebuild.

### 9.3 Persistence, recovery và resume

- Tạo working memory khi worker claim run lần đầu; liên kết `run_id` unique.
- Sau mỗi tool result: persist normalized observation, step status, counters và next state trước model call kế tiếp.
- Khi approval: snapshot chứa pending step/action ID; `ApprovalRequest` vẫn là authority cho decision.
- Worker restart: claim lease → load snapshot/version → reconcile tool receipt/event → tiếp tục từ pending step.
- Không tự retry non-idempotent tool nếu không có receipt/idempotency key. Read tool có thể retry theo registry policy.
- Khi user bổ sung thông tin ở conversation mới cho cùng ticket/incident, tạo run mới và explicit resume link; không tự ghép chỉ vì semantic similarity.

### 9.4 Context compaction

- Mỗi action/observation có stable ID như MemAct.
- Raw observations luôn durable ngoài prompt.
- Khi active observations vượt budget, `CompactionPolicy` giữ goal, unresolved contradictions, pending/failed steps, latest state per entity và verification criteria.
- Completed superseded read steps có thể chuyển thành summary với list `source_event_ids`.
- Summary là derived artifact versioned; xóa summary không xóa raw events.
- Trigger theo token pressure và step count, không theo lịch cố định duy nhất: warn ở khoảng 60% working budget, compact ở 75%, hard stop/rebuild trước 90%.

### 9.5 Working Memory khác Active Context

Working Memory là persistent complete task model dưới database constraints. Active Context là một immutable bundle cho một LLM invocation, có thể chỉ chứa 20% working memory. Khi model call kết thúc, bundle vẫn được ghi metadata/hash để reproducibility nhưng không trở thành source of truth.

---

## 10. Long-Term Memory Design

### 10.1 Semantic Memory

**Architectural proposal**

Semantic memory không nên overwrite trực tiếp một `key=value`. Dùng ba lớp:

1. `memory_sources`: immutable provenance tới message, tool receipt, CMDB/IdP/MDM record, ticket hoặc admin input.
2. `memory_assertions`: từng claim với subject/predicate/value, valid time, confidence, authority và scope.
3. `memory_facts`: materialized current view đã resolve conflict; trỏ assertion thắng và các assertion bị supersede/conflict.

Schema logic:

```yaml
MemoryAssertion:
  id: uuid
  tenant_id: uuid | null
  owner_id: uuid
  subject_type: user | device | account | service
  subject_id: string
  predicate: string
  value_json: object
  source_type: cmdb | idp | mdm | tool | user_confirmed | ticket | ai_inferred
  source_ref: string
  authority_tier: integer
  confidence: number
  valid_from: datetime
  valid_to: datetime | null
  observed_at: datetime
  status: proposed | active | contradicted | superseded | deleted | expired
  sensitivity: internal | confidential | restricted
  version: integer
```

Authority mặc định đề xuất:

```text
live authoritative tool/CMDB/IdP/MDM
  > IT-admin verified record
  > user-confirmed statement about their preference/experience
  > resolved ticket evidence
  > raw user statement
  > AI-inferred candidate
```

Thứ tự này chỉ resolve cùng predicate và overlapping validity. User preference không bị CMDB “thắng” vì chúng không cùng predicate/source domain. Conflict không bị xóa; lưu relation và hiển thị cho resolver/human khi ảnh hưởng action.

### 10.2 Episodic Memory

Episode chỉ được tạo sau một mốc đáng tin cậy: run completed với verification, resolved ticket có resolution note, hoặc technician xác nhận. Raw transcript không tự trở thành episode.

```yaml
IncidentEpisode:
  id: uuid
  tenant_id: uuid | null
  owner_id: uuid
  device_id: uuid | null
  ticket_id: uuid | null
  conversation_ids: [uuid]
  issue_signature:
    service: string | null
    product: string | null
    os: string | null
    error_codes: [string]
    symptoms: [string]
  timeline_refs: [string]
  attempted_actions:
    - action: string
      outcome: succeeded | failed | unknown
      tool_receipt_ref: string | null
  root_cause: string | null
  resolution: string | null
  verification: [string]
  final_outcome: resolved | mitigated | unresolved | false_positive
  confidence: number
  source_authority: integer
  occurred_at: datetime
  resolved_at: datetime | null
  retention_until: datetime
  embedding: vector
  schema_version: integer
```

Episode retrieval ưu tiên exact entity/error/time trước semantic similarity. Ví dụ “VPN lại không vào được” có signal recurrence, nhưng episode của thiết bị khác chỉ được dùng như experience chung nếu policy cho phép và đã de-identify; không lộ owner khác.

### 10.3 Duplicate, conflict, update, delete và expiration

- **Duplicate**: deterministic identity (`subject + predicate + normalized value + validity`) trước; embedding similarity chỉ tìm candidate.
- **Conflict**: không xóa assertion cũ. Ghi `memory_conflicts`, resolve bằng authority, validity và user/admin confirmation.
- **Update**: close `valid_to`/mark superseded rồi tạo assertion mới; fact view đổi atomically.
- **Delete**: soft delete lập tức khỏi retrieval, enqueue hard-delete/anonymization theo retention; log tombstone không chứa sensitive value.
- **Expiration**: per type/source. Live device posture có TTL ngắn; profile preference dài hơn; episode theo ticket retention/legal policy.
- **Right to correction**: API hiện tại cho edit/delete có thể được mở rộng, giữ owner scope/version checks.

---

## 11. Procedural Memory Design

### 11.1 Ranh giới

Official runbook đã publish vẫn thuộc Knowledge Base. Procedural Memory là kinh nghiệm vận hành được rút ra từ verified trajectories và được quản lý như một workflow có version. Nếu procedure mâu thuẫn policy/runbook hiện hành, policy/runbook thắng và procedure bị quarantine/deprecate.

### 11.2 Data model

```yaml
Procedure:
  id: uuid
  tenant_id: uuid | null
  key: VPN_AUTH_FAILURE
  title: string
  intent: string
  applicability:
    services: [string]
    products: [string]
    operating_systems: [string]
    error_codes: [string]
    version_range: string | null
  prerequisites: [string]
  steps:
    - id: string
      action: string
      tool_name: string | null
      expected_observation: string
      on_success: string | null
      on_failure: string | null
      permission: string | null
      approval_required: boolean
      verification: string | null
  prohibited_actions: [string]
  evidence_refs: [string]
  example_episode_ids: [uuid]
  status: candidate | review | approved | deprecated | rejected
  version: integer
  success_count: integer
  failure_count: integer
  last_validated_at: datetime | null
  approved_by: uuid | null
  effective_from: datetime | null
  effective_to: datetime | null
  embedding: vector
```

### 11.3 Extraction và publication

```text
verified completed episodes
  → cluster by issue signature
  → deterministic eligibility checks
  → LLM proposes fine-grained trace + abstract script
  → remove identities/secrets and bind evidence refs
  → sandbox replay against fixtures
  → IT/security human review
  → publish immutable version
```

Một trajectory thành công không đủ điều kiện nếu không có verification, dùng undocumented bypass, thiếu receipt, hoặc outcome chỉ do model tự khẳng định.

### 11.4 Retrieval và use

1. Hard filter tenant/scope/status/effective time/service/OS/version/required permissions.
2. Exact boost cho error code/product/version.
3. Hybrid score query/task signature với procedure title, applicability và steps.
4. Rerank theo relevance, success lower-bound, freshness và source authority.
5. Chọn tối đa 1–2 procedures để tránh plan conflict.
6. Runtime dùng procedure như plan prior; vẫn kiểm tra live state và tool policy từng bước.

### 11.5 Feedback, correction và deprecation

- Mỗi execution ghi `ProcedureExecution`: version, matched signals, steps attempted, tool receipts, outcome, verification.
- Dùng Wilson lower bound hoặc Bayesian posterior thay vì raw success ratio khi sample nhỏ.
- Failure tạo review signal; không tự rewrite approved version inline.
- Hotfix tạo version mới; old version deprecated với reason/replacement.
- Auto-deprecate candidate nếu authoritative runbook bị supersede hoặc applicability hết hạn; approved procedure cần human decision theo policy.

### 11.6 Permission

`permission` và `approval_required` chỉ là metadata giúp plan. `ToolPolicyEngine` và live principal vẫn là quyết định cuối. Procedure “unlock account” không cấp `account.unlock`; memory text không thể đổi role hoặc bỏ approval.

---

## 12. Knowledge/RAG Integration

### 12.1 Phần giữ nguyên

**Observed from code, reusable**

- Document/version lifecycle, effective/expiry, current published version.
- Company/department/IT ACL predicate áp ngay trong candidate query.
- Markdown/PDF parse, hierarchical sections, 500/60 production chunking.
- Dense + BM25/FTS + exact branches, query analysis, weighted fusion, reranker, adaptive diversity, parent/neighbor expansion.
- Evidence score/budget và citation source allowlist.

### 12.2 Contract mới giữa Knowledge và Context Manager

RAG trả `ContextCandidate[]`, không trả prompt string cuối:

```yaml
ContextCandidate:
  id: string
  kind: knowledge
  content: string
  source_ref: source_id
  relevance: number
  authority: number
  confidence: number
  valid_from: datetime
  valid_to: datetime | null
  token_cost: integer
  sensitivity: internal
  required: boolean
  conflicts_with: [string]
```

Context Manager chọn evidence vào bundle, nhưng citation store vẫn do server sở hữu. `Knowledge` không bị ghi vào LTM chỉ vì được retrieve. Một document instruction cũng không thể ra lệnh tool; prompt hiện tại đã có rule này và phải giữ.

### 12.3 Knowledge ≠ Procedure

- Runbook chính thức có thể được procedure compiler tham chiếu, nhưng source document/version vẫn độc lập.
- Procedure bị deprecate khi referenced runbook version hết hiệu lực.
- Answering policy có thể dùng knowledge trực tiếp; acting policy dùng procedure + tool policy + approval.
- Citation trong câu trả lời chỉ trỏ published knowledge. Episode/procedure provenance được hiển thị như operational rationale riêng, tránh giả làm tài liệu chính thức.

---

## 13. Context Manager

### 13.1 Interface

**Architectural proposal**

```python
class ContextManager(Protocol):
    async def build(self, request: ContextBuildRequest) -> ActiveContext: ...

class ContextBuildRequest:
    principal
    run_id
    current_request
    intent_analysis
    working_memory_version
    call_purpose       # plan | tool_selection | answer | verify | memory_decision
    model_context_limit
    reserved_output_tokens
    policy_version

class ActiveContext:
    messages
    selected_items
    excluded_items     # id + reason only
    conflicts
    token_budget
    estimated_tokens
    bundle_hash
    policy_version
```

Mọi runtime adapter phải gọi interface này trước **mỗi** LLM call. Context Manager không gọi tool side effect và không mutate memory; nó chỉ retrieve, filter, rank, compress và assemble.

### 13.2 Pipeline

```mermaid
flowchart LR
    Q[Current request + purpose] --> HF[Hard filters]
    WM[Working memory] --> HF
    H[History] --> HF
    M[Semantic + episodic] --> HF
    P[Procedures] --> HF
    K[RAG evidence] --> HF
    O[Tool observations] --> HF
    HF --> CR[Conflict resolution]
    CR --> SC[Score utility]
    SC --> DD[Deduplicate / diversify]
    DD --> B[Allocate source budgets]
    B --> CP[Compress selected overflow]
    CP --> V[Validate invariants]
    V --> AC[Immutable ActiveContext]
```

### 13.3 Hard constraints

Các điều kiện sau chạy trước scoring:

- Tenant/owner/team/document ACL và agent namespace.
- Active, not deleted, not expired; valid time overlap với current task.
- Current user request, system/tool schemas, safety policy, current goal, pending approval và verification requirements luôn giữ.
- Không đưa memory của user/device khác; cross-user episode chỉ qua de-identified team procedure đã approve.
- Không đưa AI-inferred conflict vào facts như thể confirmed.
- Tool observation phải thuộc current run hoặc explicit resume lineage.
- Latest authoritative live state thắng cached memory trong cùng predicate.
- Secrets/credentials/raw auth log bị redact hoặc chỉ reference artifact; không đưa vào model nếu không cần.
- Current request ở lượt user cuối; older content gắn source/trust tags và được coi là data.

### 13.4 Scoring cụ thể

Không dùng một weighted sum duy nhất cho mọi loại. Chọn theo hai tầng:

**Tầng A — loại và priority class**

1. P0 required: system policy, current request, current goal, pending action, unresolved conflict, last tool result needed for next transition.
2. P1 task-critical: active plan, failed/current steps, verification, live authoritative facts, direct KB evidence.
3. P2 supporting: relevant semantic facts, same-device episodes, matched procedures, recent relevant dialogue.
4. P3 optional: older dialogue, weak episodes, background metadata.

**Tầng B — score trong cùng class**

```text
utility =
    0.30 * task_relevance
  + 0.20 * next_action_utility
  + 0.15 * source_reliability
  + 0.10 * confidence
  + 0.10 * temporal_validity
  + 0.08 * recency
  + 0.07 * diversity_gain
  - token_penalty
  - conflict_penalty
```

Đây là starting policy để tune, không phải truth cố định. `source_reliability` không được semantic model tự đo. `token_penalty = min(0.25, estimated_tokens / source_budget)` để tránh item dài chiếm hết context. Exact entity/error/version match tăng `task_relevance`; cùng device/ticket tăng `next_action_utility`. Item contradicted không được chọn làm fact; nó chỉ vào conflict block nếu cần hỏi/resolve.

### 13.5 Token budget

Budget tính từ model limit sau khi reserve output và safety margin 10%. Starting allocation cho support run:

| Lane | Tỷ lệ target | Quy tắc |
|---|---:|---|
| System + tool schemas | 15% | reserved/hard |
| Current request + working memory | 25% | reserved/hard |
| Latest relevant history | 12% | recency + relevance |
| Tool observations | 18% | current/unresolved; compress old |
| Knowledge evidence | 18% | citation/evidence budget hiện có |
| Semantic + episodic memory | 7% | max per kind/entity |
| Procedure | 5% | tối đa 1–2 matched versions |

Lane có thể mượn phần thừa nhưng không vượt hard cap. Với greeting/identity request, Knowledge/Procedure lane bằng 0. Với answer-only RAG, tool observation/procedure lanes có thể bằng 0. Budget phải theo `call_purpose` thay vì một cấu hình chung.

### 13.6 KEEP/DROP/SUMMARIZE/RETRIEVE/COMPRESS

- `KEEP`: item P0/P1 hoặc utility vượt threshold và còn budget.
- `DROP`: sai scope, expired, redundant, superseded, weak/unrelated hoặc không phù hợp purpose.
- `SUMMARIZE`: group observations/messages đã hoàn tất; summary phải giữ IDs, failures, decisions và unresolved facts.
- `RETRIEVE`: khi request/working state chỉ ra missing lane; bounded call count và query không kéo topic cũ.
- `COMPRESS`: selected evidence dài nhưng cần thiết; extractive span trước, model summary sau; lưu provenance/hash.

### 13.7 Conflict resolution

1. Group claims theo normalized subject/predicate/time.
2. Nếu live authoritative source có freshness hợp lệ, chọn nó.
3. Nếu cùng authority, chọn validity overlap + newer observed/version.
4. Nếu conflict ảnh hưởng safe next action và chưa resolve, không đoán; đưa conflict block và yêu cầu clarification/live tool.
5. User statement không thể override role, ownership, service health hoặc managed configuration.

---

## 14. Memory Lifecycle

### 14.1 Pipeline và operations

```mermaid
flowchart LR
    O[Observe] --> C[Capture immutable source]
    C --> E[Extract candidates]
    E --> V[Validate schema/scope/sensitivity]
    V --> R[Retrieve similar active assertions]
    R --> D{Decision}
    D -->|ADD| A[Create assertion]
    D -->|UPDATE| U[Supersede + create version]
    D -->|DELETE| X[Tombstone / remove from retrieval]
    D -->|NOOP| N[Record decision]
    A --> S[Resolve fact view]
    U --> S
    X --> S
    S --> USE[Retrieve and use]
    USE --> CON[Consolidate episode/procedure candidate]
    CON --> EXP[Expire / deprecate / hard-delete by policy]
    D --> AUD[Audit decision + evidence + policy version]
```

### 14.2 Decision policy MVP

`MemoryDecisionEngine` là hybrid:

1. **Rules** chặn forbidden predicates, instructions, credentials, authorization claims, low provenance, cross-owner scope và duplicates exact.
2. **Retriever** lấy top similar assertions cùng subject/predicate/scope.
3. **Model** chỉ tạo typed proposal `{operation, target_id, normalized_value, rationale, evidence_refs, confidence}` khi comparison không deterministic.
4. **Validator** kiểm tra target ownership/version, source authority, temporal validity, contradiction và maximum mutation count.
5. **Gate**: user confirmation cho personal facts; IT/admin review cho operational shared facts/procedures; authoritative connector updates theo signed connector identity.
6. **Executor** mutation transaction + audit; model không ghi DB trực tiếp.

### 14.3 Synchronous và asynchronous

| Operation | Sync/async | Lý do |
|---|---|---|
| Capture current tool observation vào working memory | Sync | Cần trước next reasoning step |
| Update plan/step/hypothesis | Sync | Task correctness/recovery |
| Retrieve relevant memory/context | Sync, bounded | Cần cho call hiện tại |
| Extract semantic candidates từ user message | Async | Không chặn response; giữ behavior hiện có |
| Consolidate completed run thành episode | Async after commit | Có thể retry/idempotent |
| Cluster/distill procedure candidates | Async batch | Tốn model/compute; cần nhiều episodes |
| Expiry/deprecation/index maintenance | Async scheduled | Maintenance |
| User/admin confirm/delete | Sync transaction | UX và compliance cần kết quả rõ |

### 14.4 Audit record

Mọi decision lưu actor (`system`, user, admin, connector, model proposal), policy/prompt/model version, source refs, before/after IDs, reason code, correlation/run ID và timestamp. Không log raw secret. `NOOP` cũng cần sample/audit để đo false negative nhưng có thể dùng retention ngắn hơn.

---

## 15. Storage Architecture

### 15.1 PostgreSQL-first

**Architectural proposal**: mở rộng PostgreSQL hiện tại; không thêm graph DB/vector service trong MVP.

| Table logical | Mục đích | Index/constraint chính |
|---|---|---|
| `working_memory_snapshots` | Current durable task state | unique run; owner/tenant FK; optimistic version; JSON schema version |
| `working_memory_events` | Append-only state deltas | unique `(working_memory_id, sequence)`; dedupe key |
| `tool_observations` | Normalized result + artifact ref/receipt | unique call/idempotency key; run/owner scope |
| `memory_sources` | Immutable provenance | source type/ref unique; content hash |
| `memory_assertions` | Versioned semantic claims | subject/predicate/status/validity; vector |
| `memory_conflicts` | Explicit contradictory assertions | pair unique; resolution status |
| `incident_episodes` | Consolidated resolved/unresolved incidents | owner/device/service/error/time; vector |
| `episode_actions` | Attempt/outcome/receipt sequence | episode + ordinal unique |
| `procedures` | Stable identity | tenant + key unique |
| `procedure_versions` | Immutable workflow version | procedure + version unique; status/effective dates; vector |
| `procedure_executions` | Feedback/outcome | version/run/ticket + verified outcome |
| `memory_decisions` | ADD/UPDATE/DELETE/NOOP audit | correlation/source/operation indexes |
| `context_builds` | Bundle metadata, selection reasons, hashes/tokens | run/call sequence; short retention |

JSONB phù hợp cho versioned plan/value payload nhưng fields dùng để filter/scope/status/time phải là typed columns. Embeddings dùng pgvector cùng DB. Khi scale lớn, thêm HNSW/partition theo đo lường; không cần trước.

### 15.2 Redis và object storage

- Redis tiếp tục queue/rate limit/cache ngắn; không giữ memory duy nhất.
- Raw log bundle/PDF/tool artifact lớn nên chuyển từ local volume sang encrypted object storage ở production; DB giữ server-owned key/hash/retention/sensitivity.
- Cache retrieval key phải chứa tenant/owner/agent namespace, subject IDs, policy version và source version để tránh cross-scope leak/stale ACL.

### 15.3 Migration và compatibility

- Giữ `memory_facts` hiện có trong phase chuyển đổi; backfill thành `memory_assertions` với source type `user_confirmed`.
- `candidate_id`, conversation provenance và device scope không bị mất.
- `Conversation.issue_state` chỉ dùng compatibility/read migration; sau rollout, working state mới là typed source.
- Schema/policy/prompt versions được ghi trên snapshot/decision/context build để replay có ý nghĩa.

---

## 16. Retrieval Architecture

### 16.1 Query plan theo lane

`MemoryRetrievalPlanner` nhận latest request + intent + working entities, không nhận toàn bộ raw history. Nó sinh các bounded subqueries:

- semantic: subject/predicate/entity facts;
- episodic: issue signature + same user/device + time window;
- procedure: task intent + product/OS/error/version;
- knowledge: current request qua QueryAnalyzer hiện có;
- history: explicit references/recency.

Exact tokens (error code, ticket ID, hostname-safe identifier, version) luôn được giữ. Không kéo service từ chủ đề cũ vào query mới nếu current request tự đầy đủ.

### 16.2 Retrieval stages

1. Scope/permission/validity hard filter.
2. Exact identifiers/entity relation match.
3. Sparse + dense candidates trong từng lane.
4. Metadata boost: same device/ticket/service/OS/version/time.
5. Lane-specific rerank.
6. Conflict grouping và authority resolution.
7. Diversity theo episode/document/procedure version.
8. Context Manager cross-lane selection theo token utility.

### 16.3 Lane scoring

- Semantic fact: exact subject/predicate, authority, validity, confidence, query relevance.
- Episode: same device > same user > de-identified team pattern; same error/service/OS; recency; verified outcome.
- Procedure: applicability hard match; semantic/exact relevance; lower-bound success; freshness; approval status.
- Knowledge: giữ evidence score hiện có; không gộp score raw giữa các lane vì calibration khác nhau.

Cross-lane selector dùng priority/utility đã mô tả ở phần 13, không so `0.8` vector memory với `0.8` RAG như cùng một xác suất.

### 16.4 Fallback

- Không semantic fact: dùng live tool hoặc hỏi user; không suy từ episode khác.
- Không episode: vẫn chạy knowledge/procedure.
- Không approved procedure: model có thể lập plan mới dưới policy; không gọi candidate procedure.
- Không knowledge evidence cho internal procedure: giữ no-answer guardrail hiện tại.
- Low retrieval confidence: một rewrite/multi-query bounded; sau đó no-answer/clarification, không loop vô hạn.

---

## 17. Agent Runtime Integration

### 17.1 Runtime-neutral orchestration contract

```text
Runtime Adapter
  load WorkingMemory(version)
  loop within budgets:
    build ActiveContext(call_purpose)
    model proposes typed AgentDecision
    validate decision against state and policy
    if tool: execute → normalize observation → persist state
    if approval: persist pending action → pause
    if answer: verify completion/output → finalize
```

`AgentDecision` chỉ gồm observable fields: `decision_type`, plan delta, tool proposal, requested retrieval, answer candidate, verification status. Không yêu cầu hoặc lưu chain-of-thought.

### 17.2 OpenAI Agents SDK adapter

- Giữ SDK `Runner` và function tools.
- Tool wrapper sau mỗi result gọi `WorkingMemoryService.record_observation()`.
- Trước next inference, dùng SDK hook/session input mechanism để inject `ActiveContext`; nếu SDK không cho replace transcript an toàn, chia run thành bounded segments và resume từ app-owned state.
- SDK serialized state vẫn dùng cho exact approval interruption; working memory không phụ thuộc serialization nội bộ của SDK.
- Guard final output/citations/request policy giữ nguyên.

### 17.3 LangGraph adapter

- Graph nodes trở thành thin adapter gọi cùng services.
- Có thể gắn PostgreSQL checkpointer cho graph support runtime nếu chọn resume native; nhưng app-owned working memory vẫn là cross-runtime truth.
- Node route không cần chứa mọi procedure step; plan state quyết định next typed action, graph chỉ loop plan/act/observe/verify có bounds.
- Fake provider tiếp tục hỗ trợ deterministic tests.

### 17.4 Agent execution sequence

```mermaid
sequenceDiagram
    actor User
    participant API
    participant Worker
    participant WM as Working Memory
    participant CM as Context Manager
    participant LLM
    participant Tool as Tool Service

    User->>API: Submit request
    API->>API: Commit message + run
    API-->>Worker: Enqueue run
    Worker->>WM: Create/load snapshot
    loop bounded Plan-Act-Observe-Verify
        Worker->>CM: Build context(purpose, wm_version)
        CM-->>Worker: ActiveContext + bundle hash
        Worker->>LLM: Typed messages/tools
        LLM-->>Worker: AgentDecision
        alt tool decision
            Worker->>Tool: Execute under policy
            Tool-->>Worker: Normalized observation/receipt
            Worker->>WM: Persist observation + state transition
        else final candidate
            Worker->>WM: Verify success criteria/finalize
        end
    end
    Worker->>API: Durable events/answer available
    API-->>User: SSE + final response
```

### 17.5 Memory retrieval sequence

```mermaid
sequenceDiagram
    participant Runtime
    participant Planner as Retrieval Planner
    participant SM as Semantic Store
    participant EM as Episode Store
    participant PM as Procedure Store
    participant KB as Knowledge RAG
    participant Resolver as Scope/Conflict Resolver

    Runtime->>Planner: latest request + intent + working entities
    par scoped retrieval
        Planner->>SM: subject/predicate query
        Planner->>EM: issue signature query
        Planner->>PM: applicability/task query
        Planner->>KB: current request query
    end
    SM-->>Resolver: facts + provenance
    EM-->>Resolver: verified episodes
    PM-->>Resolver: approved versions
    KB-->>Resolver: ACL-safe evidence
    Resolver-->>Runtime: candidates + conflicts + selection metadata
```

### 17.6 Context construction sequence

```mermaid
sequenceDiagram
    participant Runtime
    participant CM as Context Manager
    participant Policy
    participant Compressor
    participant Audit as Context Build Log

    Runtime->>CM: Build(call purpose, token limit)
    CM->>Policy: Filter scope/validity/sensitivity
    Policy-->>CM: Allowed candidates + required items
    CM->>CM: Resolve conflicts, score, dedupe, allocate lanes
    opt required items exceed lane budget
        CM->>Compressor: Compress selected groups with source IDs
        Compressor-->>CM: Versioned summaries
    end
    CM->>CM: Validate invariants/current query last
    CM->>Audit: Store item IDs, reasons, tokens, bundle hash
    CM-->>Runtime: Immutable ActiveContext
```

### 17.7 Tool execution và approval sequence

```mermaid
sequenceDiagram
    participant Agent
    participant Policy as ToolPolicyEngine
    participant WM as Working Memory
    participant Approval
    participant Tool
    participant Verify

    Agent->>Policy: Tool proposal + server principal
    Policy-->>Agent: allow / approval / deny
    alt allow read
        Agent->>Tool: Execute with run/actor context
        Tool-->>Agent: Result + receipt/status
        Agent->>WM: Persist normalized observation
    else approval required
        Agent->>WM: Persist pending action + immutable args hash
        Agent->>Approval: Create request and pause
        Approval-->>Agent: Owner decision after resume
        Agent->>Policy: Recheck actor, role, args, live state
        Policy-->>Agent: allow or deny
        Agent->>Tool: Execute idempotently if allowed
        Tool-->>Agent: Receipt
        Agent->>WM: Persist outcome
    end
    Agent->>Verify: Check expected postcondition
    Verify-->>WM: Verified/failed observation
```

### 17.8 Memory consolidation sequence

```mermaid
sequenceDiagram
    participant Run as Completed Run/Ticket
    participant Job as Background Job
    participant Source as Immutable Sources
    participant MLM as Memory Lifecycle Manager
    participant Human as User/IT Reviewer
    participant Mem as Memory Stores

    Run-->>Job: After-commit consolidation event
    Job->>Source: Load scoped events, receipts, verification
    Source-->>MLM: Evidence bundle
    MLM->>MLM: Extract + dedupe + compare + propose operation
    alt personal semantic fact
        MLM-->>Human: User confirmation candidate
    else incident episode with verified outcome
        MLM->>Mem: Store versioned episode
    else procedure candidate
        MLM-->>Human: IT/security review + sandbox evidence
    end
    Human-->>MLM: Confirm/edit/reject
    MLM->>Mem: Transactional mutation + audit decision
```

### 17.9 End-to-end: “VPN của tôi lại không vào được”

1. API xác định principal từ session và tạo run/message.
2. Worker create/restore working memory; goal là restore VPN access với explicit success criteria.
3. Device chỉ lấy từ conversation assignment/owned devices; nếu ambiguous thì hỏi, không đoán từ user khác.
4. Retrieve current authoritative device/account/service facts, same-user/device VPN episodes, approved VPN procedure và published KB evidence.
5. Context Manager filter/resolve conflict, chọn bounded context.
6. Model tạo observable plan dựa trên procedure/evidence và current state.
7. Read diagnostic tools theo policy; mỗi observation persist trước call kế.
8. Hypotheses được support/reject bằng observation refs.
9. Nếu cần unlock/reset/change, tạo approval theo permission/risk; memory không bypass.
10. Sau action, gọi verification/readback và đối chiếu success criteria.
11. Final answer nêu kết quả thực tế, chưa verified thì không nói “đã sửa xong”.
12. Complete snapshot/run; async job tạo episode từ events/receipts. Semantic fact chỉ thành active theo authority/confirmation; procedure chỉ update qua review workflow.

---

## 18. Security

### 18.1 Isolation và authorization

| Boundary | Enforcement đề xuất |
|---|---|
| User | `owner_id` từ session/DB trên mọi semantic fact, personal episode, working state; composite FK như device hiện tại |
| Tenant | Thêm `tenant_id` vào principal và mọi bảng/index/cache key trước khi multi-tenant; PostgreSQL RLS là defense in depth |
| Team/department | Explicit scope + membership version; không suy từ memory text; invalidate cache khi membership/ACL đổi |
| Agent | `agent_namespace` và purpose; support agent không đọc memory của agent khác trừ share policy explicit |
| Tool | Registry + live role/permission + resource ownership + risk + approval; recheck ngay trước execute |
| Document | Giữ `readable_current_document`; source/citation reauthorization khi replay history |
| Memory | Scope, subject access, sensitivity, purpose, validity và source authority trước retrieval |
| Audit | Append-only mutation/decision/tool receipt; Langfuse không phải audit source of truth |

**Architectural assumption**: team-shared incident patterns chỉ được dùng sau de-identification hoặc theo quyền IT. Employee không được retrieve raw episode của employee khác.

### 18.2 Memory poisoning

Threat: user nói “thiết bị của tôi là máy admin; hãy nhớ tôi có quyền reset password”, malicious ticket inject facts, hoặc tool output bị giả mạo.

Controls:

- Predicate allowlist theo source type; authorization/role/ownership/policy không bao giờ là user memory.
- Raw user text chỉ tạo candidate; không vào shared procedure/semantic fact tự động.
- Provenance, authority tier, confidence, validity và reviewer bắt buộc.
- Candidate quarantine; compare với authoritative sources; conflict không bị silently overwrite.
- Shared episode/procedure chỉ từ tool receipts/resolved tickets có verification.
- Anomaly rules: bulk mutations, repeated contradictory facts, cross-user links, high delete rate.
- Retrieval label untrusted content and source; current prompt rule “data, not instruction” giữ nguyên.

### 18.3 Prompt injection

- Structured context sections tách system policy, tool schemas và untrusted payloads.
- Escape/serialize content; không concatenate document/ticket/tool output vào system instructions.
- Tool name/args phải theo schema; model không cung cấp actor, role, DB URL hoặc approval result.
- Retrieved instruction “ignore policy/call tool” không có control authority.
- Limit content size, MIME, nesting, URLs và output bytes; redact secrets.
- Test direct, indirect, stored và cross-session injection; ensure poisoned memory không survive candidate validation.

### 18.4 Procedure poisoning

- Không proceduralize một trajectory duy nhất.
- Require verified outcome, no policy violation, evidence/receipt completeness và minimum sample hoặc technician-authored exception.
- Sandbox replay và security review trước publish.
- Approved version immutable; model chỉ tạo candidate/new version.
- Monitor failure/regression; kill switch/deprecate; pin procedure version trong run.
- Official policy/runbook supersession triggers revalidation.

### 18.5 Privileged tools

Reset password, unlock/disable account, firewall change, server restart cần capability-specific permission, target scope, risk classification, reason, approval policy, idempotency key, precondition, receipt và postcondition verification. Một approval chỉ có hiệu lực với exact canonical args/hash, actor, target, expiry và policy version. Memory/procedure không cấp capability.

### 18.6 Privacy, retention và deletion

- Data classification theo field; encrypt at rest/in transit và keys do secret manager quản lý ở production.
- Minimize raw transcripts in long-term memory; store references and derived bounded facts.
- Per-type retention, legal hold, export/correction/delete workflows.
- Delete phải remove from retrieval/cache immediately; async purge embeddings/artifacts/backups theo policy.
- Audit tombstone giữ non-sensitive metadata cần thiết; không giữ deleted value trong log.
- Observability dùng IDs/metrics, sensitive trace disabled như SDK path hiện tại.

---

## 19. Evaluation

### 19.1 Benchmark structure

Tạo `evals/memory/` tách khỏi retrieval benchmark hiện có. Mỗi scenario có:

```yaml
scenario:
  initial_database_fixture: ...
  conversations_sessions: ...
  current_request: ...
  interruptions: [worker_crash, approval_wait, user_followup]
  tools:
    responses: ...
    faults: ...
  expected:
    final_state_predicates: ...
    allowed_tool_calls: ...
    forbidden_tool_calls: ...
    required_evidence: ...
    memory_operations: ...
    answer_constraints: ...
```

Theo tinh thần ITBench, chấm **environment state và receipts** thay vì chỉ LLM judge. Bộ đầu tiên nên có VPN, GitLab, registry, account/ticket, ambiguous device, stale service state, conflicting device fact, repeated incident, approval reject, crash/resume và injection.

### 19.2 Memory Quality

| Metric | Cách đo |
|---|---|
| Retrieval Precision@k / Recall@k | Gold relevant semantic/episode/procedure IDs theo scenario |
| Memory relevance | Selected relevant tokens / total memory tokens; human adjudication sample |
| Fact consistency | Contradictory active facts per subject/predicate/time; target 0 cho authoritative conflicts |
| ADD/UPDATE/DELETE/NOOP macro F1 | Gold lifecycle decisions, report per operation |
| Update correctness | New value/source/validity đúng và old assertion superseded đúng |
| Delete correctness | Ngay lập tức không retrieve + eventual purge SLA |
| Conflict resolution accuracy | Correct winner/clarification/quarantine theo authority policy |
| Provenance completeness | % active fact/episode/procedure có resolvable source refs |
| Unauthorized memory recall | Cross-owner/tenant/team retrieval count; target 0 |

### 19.3 Context Management

- Input tokens/call, total tokens/task, p50/p95 context build latency.
- Compression ratio = original eligible tokens / selected tokens.
- Critical information retention recall: goal, failed step, pending approval, latest observation, exact error code, verification.
- Distractor inclusion rate và stale/superseded inclusion rate.
- Context bundle reproducibility by stored IDs/policy/model versions.
- Answer/task quality at matched token budgets.
- Compaction hallucination/omission rate; every summary claim must map to source event IDs.

### 19.4 Agent Performance

- End state task success rate, verified completion rate.
- Correct tool/argument/target rate; forbidden tool rate.
- Duplicate tool calls, unnecessary actions, turns and wall time.
- Approval compliance and false success claim rate.
- Recovery success after process crash, lease loss, network timeout and approval wait.
- Multi-step success stratified by 3/5/10/20 tool observations.
- No-answer/clarification correctness and knowledge citation coverage.

### 19.5 Procedural Memory

- Procedure Recall@k/MRR by issue signature.
- Success uplift and step reduction versus no procedure.
- Reuse rate, incorrect procedure rate, applicability mismatch rate.
- Safety violation/approval bypass rate; target 0.
- Time-to-deprecate after runbook supersession.
- Calibration: predicted success band versus observed verified success.

### 19.6 Evaluation gates

MVP promotion gate đề xuất:

- 0 cross-scope retrievals và 0 approval bypasses trong security suite.
- ≥99% critical state retention after compaction on deterministic fixtures.
- ≥95% crash/resume state recovery for injected interruption points; no duplicate writes.
- Memory operation macro F1 ≥0.85 offline, DELETE recall 1.0 for explicit user deletion cases.
- No statistically significant regression in current RAG no-answer/scope leakage/citation metrics.
- Task success improvement must be accompanied by bounded token/latency cost; report confidence intervals, not one run.

### 19.7 Ablation study

Chạy cùng frozen scenario split, model/version/temperature/tool fixtures và multiple seeds:

| Variant | Thành phần bật | Câu hỏi |
|---|---|---|
| A0 | Agent only | Model/tool loop cơ sở làm được gì? |
| A1 | A0 + RAG | Official knowledge cải thiện answer/task bao nhiêu? |
| A2 | A1 + Working Memory/Context Manager | Long-horizon, token và recovery cải thiện không? |
| A3 | A2 + Semantic/Episodic LTM | Recurring incident/personalization có tốt hơn mà không leak không? |
| A4 | A3 + Procedural Memory | Success/steps/cost có cải thiện trên analogous unseen tasks không? |

Thêm ablations nội bộ: recency-only vs score policy; no conflict resolver; trajectory-only vs script-only vs combined procedure; rule lifecycle vs rule+model proposal. Dùng paired bootstrap/confidence interval và công bố failures, token, latency, tool side effects cùng success rate.

---

## 20. Implementation Roadmap

### Priority summary

| Priority | Nội dung |
|---|---|
| Must Have | Phase 0–3: contracts/benchmark, working memory, context manager, semantic/episodic lifecycle/audit |
| Should Have | Phase 4: approved procedural memory; production connector authority |
| Future Research | Phase 5–6: learned context/memory policy, graph expansion, multi-agent shared memory |

Không rollout toàn bộ cùng lúc. Mỗi phase chạy shadow/evaluation trước khi ảnh hưởng answer/action.

### Phase 0 — Contracts, threat model và baseline

**Objective**: khóa taxonomy, interfaces, metrics và security invariants trước migration.

- **Architecture changes**: thêm design contracts và eval harness; không đổi serving behavior.
- **Component thêm**: `ContextCandidate`, `ActiveContext`, `WorkingMemorySnapshot`, lifecycle decision schemas; scenario runner.
- **Component sửa**: chưa đổi runtime; instrument current context selection làm baseline.
- **Data model/storage**: chỉ `context_builds` hoặc file report trong shadow; chưa lưu sensitive content.
- **API/interface**: provider/runtime-neutral protocols; versioned JSON schemas.
- **Dependencies**: không thêm service/library bắt buộc.
- **Testing**: fixtures multi-session, conflict, injection, crash/approval, 3–20 tool steps; current regression suite.
- **Acceptance criteria**: current architecture inventory được review; gold scenarios/metrics frozen; security/product xác nhận authority/retention.
- **Risk/trade-off**: mất thời gian trước feature nhưng ngăn schema drift và benchmark tự chấm theo implementation.
- **Estimated complexity**: M (1–2 sprint tùy gold labeling).

### Phase 1 — Durable Working Memory

**Objective**: task dài không quên goal/plan/observations và resume được sau crash/approval.

- **Architecture changes**: app-owned snapshot + append-only state events quanh cả hai runtime.
- **Component thêm**: `WorkingMemoryService`, transition validator, normalized observation/receipt adapter, compaction metadata.
- **Component sửa**: worker tạo/load/persist state; tool wrappers record observation; run finalization/approval resume reconcile state.
- **Data model/storage**: `working_memory_snapshots`, `working_memory_events`, `tool_observations`; optimistic version + run/owner FK.
- **API/interface**: internal `load`, `apply_transition`, `record_observation`, `pause`, `resume`, `complete`; optional read-only debug/admin view không chứa secret.
- **Dependencies**: PostgreSQL hiện có; không thêm queue.
- **Testing**: transition property tests, concurrent update, lease loss, duplicate result, crash at every boundary, approval resume, raw artifact size/redaction.
- **Acceptance criteria**: recovery gate ≥95%, duplicate write 0, goal/pending/verification retention ≥99%, current UI/API contract không đổi.
- **Risk/trade-off**: dual state giữa SDK/LangGraph và DB; giải bằng DB truth + adapter reconciliation.
- **Estimated complexity**: L (2–4 sprint).

### Phase 2 — Unified Context Manager

**Objective**: mọi model call nhận active context có scope, budget, relevance và provenance thống nhất.

- **Architecture changes**: thay direct history assembly bằng `ContextManager`; lane budget/call purpose; addressable compaction.
- **Component thêm**: candidate adapters, hard filter, scorer, conflict resolver, budget allocator, summary artifact/version, context build metrics.
- **Component sửa**: `build_agent_context` trở thành history adapter hoặc được thay dần; Agents SDK hooks/segmentation; LangGraph nodes; RAG trả candidates.
- **Data model/storage**: `context_builds`, summary artifacts; item IDs/reasons/hash, retention ngắn.
- **API/interface**: `build(ContextBuildRequest) -> ActiveContext`; `explain(bundle_id)` cho internal debugging có authorization.
- **Dependencies**: tokenizer phù hợp model nên thêm sau benchmark; MVP có adapter estimator fallback.
- **Testing**: latest-query isolation, exact token retention, budget overflow, conflict, source lane borrowing, 30 tool observations, prompt injection, deterministic replay.
- **Acceptance criteria**: no scope leakage; ≥99% critical retention; giảm token ở long-horizon mà task success không giảm; cả hai runtime dùng cùng policy.
- **Risk/trade-off**: SDK transcript khó replace giữa turn; có thể segment run, tăng orchestration code nhưng giữ app control.
- **Estimated complexity**: L (3–5 sprint).

### Phase 3 — Semantic + Episodic Memory và lifecycle

**Objective**: memory có provenance/authority/conflict; resolved work trở thành episode có thể retrieve.

- **Architecture changes**: source/assertion/fact-view model; generalized ADD/UPDATE/DELETE/NOOP; async episode consolidation.
- **Component thêm**: `MemoryDecisionEngine`, source registry, conflict resolver, assertion/fact repositories, episode consolidator/retriever, audit service.
- **Component sửa**: memory extraction jobs; UI/API candidate/fact views; ticket/run completion dispatch; SupportContext chuyển sang Context Manager.
- **Data model/storage**: source/assertion/conflict/episode/action/decision tables + vector; migrate existing confirmed facts.
- **API/interface**: list/explain/correct/delete fact; list episode summaries; admin conflict review; connector ingestion identity.
- **Dependencies**: pgvector hiện có; model extraction optional/bounded; chưa cần graph DB.
- **Testing**: provenance, authority conflicts, temporal facts, duplicate/idempotency, cross-device/user isolation, deletion purge, episode consolidation from verified/unverified tickets.
- **Acceptance criteria**: lifecycle macro F1 ≥0.85; explicit delete recall 1.0; provenance completeness ≥99%; current memory consent semantics preserved; no RAG regression.
- **Risk/trade-off**: schema/lifecycle phức tạp hơn simple key-value; đổi lại có correctness/audit cần cho enterprise.
- **Estimated complexity**: XL (4–7 sprint).

### Phase 4 — Procedural Memory

**Objective**: reuse verified troubleshooting workflows mà không biến experience thành authorization.

- **Architecture changes**: offline trajectory pipeline → candidate → sandbox/review → immutable procedure version → runtime retrieval/feedback.
- **Component thêm**: procedure compiler, registry, retriever, review workflow, execution tracker, deprecation monitor.
- **Component sửa**: working plan có `procedure_version_id`; Context Manager procedure lane; tool execution captures expected/postcondition.
- **Data model/storage**: procedures, versions, steps/applicability, executions, reviews.
- **API/interface**: IT/admin candidate review/publish/deprecate; internal retrieve; metrics dashboard.
- **Dependencies**: existing Celery/background worker; sandbox fixtures; no model training.
- **Testing**: applicability/version, unsafe trajectory rejection, runbook supersession, approval enforcement, trajectory/script/combined ablation.
- **Acceptance criteria**: 0 approval bypass; statistically credible task-success or step-cost uplift on held-out analogous tasks; incorrect procedure below agreed threshold; rollback/deprecate works.
- **Risk/trade-off**: procedure poisoning và automation bias; human review làm chậm publication nhưng cần thiết.
- **Estimated complexity**: XL (4–8 sprint cộng thời gian review dữ liệu).

### Phase 5 — Advanced consolidation and learned policies

**Objective**: chỉ xử lý bottleneck đã đo được.

- **Architecture changes**: thử learned memory distillation/context policy ở shadow hoặc offline.
- **Component có thể thêm**: calibrated reranker, graph link table, memory clustering, model-based compaction verifier, policy evaluation service.
- **Component sửa**: selector/lifecycle behind feature flags; không thay source/audit contracts.
- **Data model/storage**: derived links/clusters/model scores có version; có thể vẫn ở PostgreSQL.
- **API/interface**: offline train/eval artifact registry, feature flag/canary.
- **Dependencies**: model training stack chỉ khi approved; graph DB chỉ khi relational link query không đạt SLO.
- **Testing**: replay, counterfactual deletion, poisoning, calibration, fairness, cost/latency, rollback.
- **Acceptance criteria**: vượt deterministic baseline trên held-out tasks và security gates, có rollback trong một deploy/config change.
- **Risk/trade-off**: distribution shift, opaque deletion, training/serving cost. AgeMem/MemAct/Memory-R1 RL nằm ở đây.
- **Estimated complexity**: XL/Research.

### Phase 6 — Multi-Agent Shared Memory

**Objective**: hỗ trợ specialist agents mà không leak hoặc race state.

- **Architecture changes**: coordinator owns working memory; agents có private namespace và read/write capability explicit; shared facts qua mediated commit.
- **Component thêm**: agent registry, delegation/task contracts, memory namespace policy, merge/conflict coordinator.
- **Component sửa**: principal thành actor chain (user/service/agent); audit/handoff events; context purpose per specialist.
- **Data model/storage**: agent namespace, delegation, shared-memory proposal/commit, causal/version metadata.
- **API/interface**: `delegate`, `propose_memory`, `commit_shared_memory`; không cho arbitrary shared write.
- **Dependencies**: chưa xác định; không cần trong single-agent product hiện tại.
- **Testing**: confused deputy, cross-agent prompt injection, concurrent proposals, cancellation, partial failure, ownership.
- **Acceptance criteria**: chỉ bắt đầu khi single-agent baseline ổn và có use case/SLO rõ; 0 unauthorized cross-agent reads/writes.
- **Risk/trade-off**: coordination cost và attack surface lớn; giữ **Future Research**.
- **Estimated complexity**: XXL/Research.

### Rollout strategy

Mỗi phase: schema dark launch → shadow write/read → offline replay → canary staff tenant → feature flag gradual rollout → rollback drill. Không migrate/delete old facts cho tới khi dual-read comparison và user-facing correction/delete đã qua acceptance.

---

## 21. Architectural Decisions

| ID | Quyết định | Lý do |
|---|---|---|
| MD-01 | PostgreSQL là source of truth cho working/LTM/procedure | Stack đã có transactions, owner FK, pgvector, backup; giảm operational surface |
| MD-02 | App-owned working memory độc lập runtime serialization | Resume/cross-runtime/schema evolution không phụ thuộc SDK internals |
| MD-03 | Context Manager dựng bundle trước mỗi model call | Context là view theo purpose; tránh transcript accumulation và policy drift |
| MD-04 | Model proposes, server validates/executes memory mutations | Audit, authority, deletion và isolation cần deterministic enforcement |
| MD-05 | Immutable source + versioned derived memory | Cho phép correction, replay, conflict và chống hallucinated overwrite |
| MD-06 | Authority/validity là hard logic, similarity chỉ là retrieval signal | CMDB/live tool phải thắng remembered/inferred claim |
| MD-07 | Episode chỉ từ verified/consolidated outcome | Raw transcript/ticket không đủ causal reliability |
| MD-08 | Procedure cần review; không cấp permission | Ngăn procedure poisoning và confused deputy |
| MD-09 | Giữ Knowledge, Memory và Procedure thành index/store logic riêng | Lifecycle, trust, retrieval và citation khác nhau |
| MD-10 | Rules-first; RL/learned policy sau ablation | Project chưa có trajectories/reward/security evidence đủ để train |
| MD-11 | Single agent MVP; namespace-ready data model | Code chưa có multi-agent use case; tránh over-engineering |
| MD-12 | Không lưu chain-of-thought | Không cần cho recovery/audit; lưu plan, observation, decision và evidence refs đủ |

---

## 22. Alternatives

### 22.1 Dùng toàn bộ conversation history

**Reject**: đơn giản nhưng token/latency tăng, attention dilution, topic leakage và prompt injection persistence. Current builder đã chứng minh hướng bounded context đúng.

### 22.2 Dùng SDK session/checkpoint làm toàn bộ memory

**Reject**: serialized state phù hợp exact runtime resume nhưng không phải stable business schema, khó query/audit/migrate/cross-runtime và có thể chứa transcript dư thừa.

### 22.3 Dùng `Conversation.issue_state` JSONB làm working memory

**Reject làm đích**, có thể bridge migration: thiếu typed transition, event lineage, unique run relationship và concurrency semantics rõ.

### 22.4 Mọi memory đều là vector text

**Reject**: vector similarity không resolve authority, temporal validity, exact entity/error, permissions hoặc deletion. Dùng relational filters + typed metadata + vector candidate retrieval.

### 22.5 Graph database ngay từ đầu

**Reject cho MVP**: A-MEM/Mem0 graph cho ý tưởng links, nhưng repository hiện chưa có workload chứng minh multi-hop graph cần service mới. Relational link tables và recursive CTE đủ để đo trước.

### 22.6 End-to-end RL memory manager ngay

**Future**: AgeMem/MemAct/Memory-R1 cho thấy tiềm năng, nhưng cần verified trajectories, reward chống unsafe side effects, training/serving infra và audit. MVP rules + model proposal có rollback và dễ đánh giá hơn.

### 22.7 Mua managed memory service

**Không chọn mặc định**: có thể rút ngắn feature time nhưng làm khó data residency, owner/tenant scoping, authority conflict, deletion proof và integration với ticket/tool receipts. Chỉ evaluate qua interface `MemoryService` với security/compliance benchmark.

### 22.8 Đưa runbook vào procedural memory và bỏ KB

**Reject**: mất document authority/version/citation. Official runbook vẫn là knowledge; procedure tham chiếu nó và có operational feedback riêng.

---

## 23. Risks

| Risk | Probability / Impact | Mitigation / trigger |
|---|---|---|
| Context Manager bỏ mất chi tiết critical | M/H | P0 invariants, event IDs, critical-retention tests, raw state ngoài prompt |
| Summary hallucination | M/H | extractive-first, provenance mapping, verifier, never replace raw source |
| Conflicting/stale facts | H/H | authority + temporal model, live tool precedence, explicit conflict state |
| Memory poisoning | M/H | candidate quarantine, source predicate allowlist, confirmation/review, anomaly audit |
| Procedure poisoning/automation bias | M/Critical | verified outcomes, sandbox, human publish, approval policy, kill switch |
| Cross-user/tenant leakage | L/Critical | composite scopes/RLS/cache keys/security tests; block multi-tenant until tenant model exists |
| Duplicate side effects after recovery | L/Critical | receipt/idempotency, reconcile before retry, existing approval pattern |
| Dual runtime drift | H/M | shared contracts/services/conformance suite; runtime adapters stay thin |
| Model/prompt version changes behavior | H/M | record versions, replay suite, canary/feature flags |
| Storage/index growth | M/M | per-type retention, partition/ANN only after SLO metrics, archive raw artifacts |
| Latency/cost from multi-lane retrieval | M/M | parallel bounded reads, lane gating by intent/purpose, cache with scope/version keys |
| User confusion about remembered data | M/M | explain provenance, confirmation/edit/delete UX, no false “saved” claim |
| RL optimizes task success over safety | Future/Critical | constrained rewards, hard server policy, offline/canary only; no learned authorization |
| Existing docs/code drift | M/M | ADR + executable conformance tests; code observations take precedence over stale PLAN text |

---

## 24. Open Questions

Các câu hỏi dưới đây cần product/security/operations quyết định trước phase tương ứng; chúng không chặn Phase 0 inventory/evaluation.

1. Sản phẩm sẽ giữ single-company hay cần tenant isolation trong 6–12 tháng? Nếu có khả năng SaaS, thêm `tenant_id` từ migration đầu.
2. Nguồn authoritative nào thực sự tồn tại: CMDB, MDM, IdP, VPN controller, endpoint agent? Authentication và freshness SLA của từng connector là gì?
3. User có được xem/delete mọi episode liên quan mình không, hay ticket retention/audit/legal hold giới hạn quyền này?
4. Personal memory cần explicit confirm cho mọi fact hay có thể auto-accept low-risk preference? Đề xuất mặc định hiện tại là giữ explicit confirm.
5. Ticket nào được coi “verified resolved”: technician status, tool postcondition, user confirmation, hay kết hợp?
6. Ai có quyền publish/deprecate procedure: IT lead, security, service owner? Có cần four-eyes approval cho privileged procedure không?
7. Có được dùng de-identified cross-user episodes để tạo team procedure? Chuẩn de-identification và minimum cohort là gì?
8. Model context limit/model family production mục tiêu là gì để đặt absolute budgets và tokenizer chính xác?
9. SLO cho context build/retrieval và toàn run là bao nhiêu? Có chấp nhận model call phụ cho compression/memory decision không?
10. Retention theo type/sensitivity và yêu cầu backup deletion là gì?
11. Người dùng/IT cần “Why was this remembered/retrieved?” ở mức nào trong UI?
12. `AgentRun` mới cho mỗi follow-up hay một long-lived incident có nhiều runs? Đề xuất: nhiều immutable runs liên kết một incident/working task.
13. LangGraph sẽ tiếp tục là production rollback lâu dài hay chỉ test/fake path? Điều này quyết định mức conformance adapter cần duy trì.
14. Evaluation scenarios có thể dùng sandbox/tool simulator nào để chấm state changes an toàn và reproducible?
15. Ngưỡng business nào chứng minh Procedural Memory đáng triển khai: task success uplift, giảm steps, giảm escalation hay giảm MTTR?

---

## Appendix A — Traceability tới code hiện tại

| Chủ đề | File/symbol chính |
|---|---|
| Graph state/bounds | `backend/app/agent/state.py::SupportAgentState` |
| LangGraph topology | `backend/app/agent/graph.py::build_support_graph`, `run_support_graph` |
| Agents SDK loop/input | `backend/app/agent/openai_agents_runtime.py::build_agents_input`, `OpenAIAgentsRuntime` |
| Runtime contract | `backend/app/agent/runtime.py::AgentRuntime`, `AgentRuntimeResult` |
| Worker composition | `backend/app/jobs/worker.py::execute_agent_run` |
| Context load/build | `backend/app/agent/context/service.py`, `builder.py`, `summary.py` |
| Memory lifecycle/retrieval | `backend/app/memory/lifecycle.py`, `retrieval.py`, `extractor.py` |
| Tool registry/policy/execution | `backend/app/tools/registry.py`, `policy.py`, `executor.py` |
| Approval/resume | `backend/app/services/approvals/*`, `services/conversations/agent_runtime_state.py` |
| RAG ingestion/retrieval/citations | `backend/app/rag/ingestion/*`, `retrieval/*`, `citations/sources.py` |
| Persistence models | `backend/app/db/models.py`; migrations `0013`–`0020` |
| Prompt safety | `backend/app/prompts/agent.md` |
| Infra/observability | `infra/compose.yaml`, `backend/app/observability.py`, `jobs/celery_app.py` |

## Appendix B — Research sources

- Yi Yu et al., [Agentic Memory: Learning Unified Long-Term and Short-Term Memory Management for Large Language Model Agents](https://aclanthology.org/2026.acl-long.981/), ACL 2026.
- Yuxiang Zhang et al., [Memory as Action: Autonomous Context Curation for Long-Horizon Agentic Tasks](https://aclanthology.org/2026.findings-acl.956/), Findings of ACL 2026.
- Charles Packer et al., [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560), 2023/2024 revision.
- Prateek Chhikara et al., [Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory](https://arxiv.org/abs/2504.19413), 2025.
- Wujiang Xu et al., [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110), NeurIPS 2025.
- Sikuan Yan et al., [Memory-R1: Enhancing Large Language Model Agents to Manage and Utilize Memories via Reinforcement Learning](https://aclanthology.org/2026.acl-long.583/), ACL 2026.
- Runnan Fang et al., [Memp: Exploring Agent Procedural Memory](https://arxiv.org/abs/2508.06433), Findings of ACL 2026.
- Saurabh Jha et al., [ITBench: Evaluating AI Agents across Diverse Real-World IT Automation Tasks](https://proceedings.mlr.press/v267/jha25a.html), ICML 2025.

