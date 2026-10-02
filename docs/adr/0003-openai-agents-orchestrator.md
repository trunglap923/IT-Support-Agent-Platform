# ADR-0003 — OpenAI Agents SDK orchestrator và approval có thể resume

Ngày: 2026-10-02
Trạng thái: chấp nhận; P0–P2 đã được triển khai.

## Bối cảnh

LangGraph hiện tại chạy một graph do ứng dụng định nghĩa. Cách này phù hợp với fake mode và
workflow cố định, nhưng mỗi bước tool phải được mô tả trước trong graph. Sản phẩm cần một Agent có
thể tự chọn chuỗi read tool phù hợp với từng câu hỏi, quan sát kết quả rồi quyết định gọi tool tiếp
hay trả lời. Luồng tạo ticket vẫn phải giữ owner scope, policy và xác nhận của người dùng.

## Quyết định

- Dùng một orchestrator dựa trên OpenAI Agents SDK khi `TEXT_PROVIDER=openai` và
  `AGENT_RUNTIME=auto|openai_agents`.
- Giữ LangGraph cho fake mode và làm đường rollback bằng `AGENT_RUNTIME=langgraph`.
- Giới hạn một run ở 6 model turn và 4 read tool call. Agent không được xuất chain of thought;
  frontend chỉ nhận các event tiến trình an toàn theo tên công việc.
- Tách `SupportContextService` để dựng request, hội thoại, thiết bị và memory trong owner scope.
  Knowledge retrieval vẫn là một tool riêng, chỉ trả source ID và excerpt đã qua ACL.
- Mọi business read đi qua `ToolExecutor`, registry schema, output validation và `ToolPolicyEngine`.
  Tool tạo ticket dùng cùng policy metadata và luôn yêu cầu approval.
- Dùng cơ chế interruption của Agents SDK. Snapshot được lưu trong bảng
  `agent_runtime_states`; approval vẫn dùng `approval_requests` và hash arguments hiện có. Worker
  mới có thể nạp snapshot, áp quyết định approve/reject và chạy tiếp đúng run.
- Việc ghi ticket tiếp tục qua `TicketWriteService.create_from_approval`, nên retry hoặc delivery
  trùng vẫn quy về receipt duy nhất.

## Luồng thực thi

```text
request đã commit
  -> worker claim lease
  -> SupportContextService
  -> Agents SDK: model -> read tool -> model -> ...
  -> final structured answer

create_ticket
  -> ToolPolicyEngine
  -> SDK interruption
  -> lưu ApprovalRequest + RunState snapshot
  -> user approve/reject
  -> worker nạp snapshot
  -> SDK tiếp tục
  -> TicketWriteService hoặc câu trả lời từ chối
```

## An toàn và quan sát

- Actor, role và run ID do worker lấy từ database; model không được truyền các trường này.
- MCP subprocess revalidate actor/run trước mỗi read tool.
- Citation cuối chỉ được nhận nếu source ID có trong evidence store của chính run.
- Tool input/output dùng Pydantic schema; kết quả lặp, quá thời gian, vượt kích thước hoặc sai schema
  được trả thành lỗi có mã ổn định.
- Progress event chỉ gồm stage, trạng thái và mô tả ngắn. Prompt, memory, tool payload và suy luận ẩn
  không được đưa vào event.
- Paid call tiếp tục reserve/complete qua usage ledger; OpenAI client tắt SDK retry và `store=false`.

## Hệ quả

- OpenAI mode có tool loop động giống Agent SDK chuẩn, trong khi fake mode vẫn deterministic và
  không cần API key.
- Cần chạy migration `0019_agent_runtime_state` trước khi bật runtime mới.
- Snapshot SDK là state nội bộ và phụ thuộc schema/version thư viện. Rollout cần giữ dependency
  `openai-agents` trong lockfile và hoàn tất các approval đang chờ trước khi nâng phiên bản lớn.
- Chưa tách sub-agent. Asset action, password reset và remote execution chưa được cấp cho model.
- Structured final output hiện được đẩy lên UI khi hoàn tất; tool progress vẫn stream theo thời gian
  thực qua SSE.

## Cấu hình vận hành

| `TEXT_PROVIDER` | `AGENT_RUNTIME` | Runtime |
|---|---|---|
| `fake` | `auto` hoặc `langgraph` | LangGraph |
| `openai` | `auto` hoặc `openai_agents` | OpenAI Agents SDK |
| `openai` | `langgraph` | LangGraph rollback |

`AGENT_RUNTIME=openai_agents` với fake text provider bị từ chối ngay khi nạp settings.
