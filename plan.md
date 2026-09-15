# IT Support Agent Platform — Kế hoạch triển khai

Phiên bản kế hoạch: 2.0  
Ngày chốt thiết kế: 2026-09-15  
Trạng thái: đặc tả để bắt đầu viết code; các con số chất lượng là mục tiêu cần đo.  
Bản kế hoạch ban đầu: [docs/archive/plan-original.md](docs/archive/plan-original.md).

Bộ khung thư mục và WP-01 đã được triển khai, kiểm tra local. Xem [README](README.md), [roadmap và mục lục các PLAN.md](docs/implementation-roadmap.md) để chạy code và bắt đầu WP-02. M0 vẫn chưa hoàn thành vì còn các spike OpenAI/MCP/checkpointer, seed spec và evaluation cases.

## 1. Mục tiêu và những lựa chọn đã chốt

### 1.1. Yêu cầu của người xây dựng

| Nội dung | Lựa chọn đã xác nhận |
|---|---|
| Mục tiêu | Portfolio xin việc, có luồng nghiệp vụ hoàn chỉnh và bằng chứng kiểm thử |
| Nhân lực | Một người, đã có nền tảng Python/backend |
| Tiến độ | Ưu tiên hoàn thành sớm, có demo chạy được từ các mốc đầu |
| Giao diện | Web chat, danh sách ticket, quản lý tài liệu |
| Dữ liệu | Bộ dữ liệu tự tạo và dịch vụ mô phỏng; có thể bổ sung PDF công khai |
| AI | OpenAI API, ưu tiên tiết kiệm |
| Thành phần bắt buộc | MCP, LangGraph, memory qua nhiều cuộc trò chuyện, Redis, Langfuse |

### 1.2. Những quyết định kỹ thuật của bản kế hoạch

- Một doanh nghiệp giả lập, hai phòng ban để kiểm thử phân quyền. Chưa xây SaaS nhiều tenant.
- Ba nhóm vấn đề: VPN, Docker/internal registry, GitLab.
- Giao diện mặc định tiếng Việt; hiểu câu hỏi và tài liệu Việt/Anh.
- Một agent có graph và giới hạn số bước; bốn tool được cung cấp cho model.
- FastAPI và React/TypeScript; các tiến trình Python dùng chung codebase và Docker image.
- PostgreSQL là nguồn dữ liệu chính; Redis phục vụ queue, rate limit và cache có giới hạn.
- Ticket được lưu thật trong database của ứng dụng. Nguồn trạng thái dịch vụ được mô phỏng.
- Langfuse Cloud dùng cho V1; self-host Langfuse là hạng mục mở rộng.
- Mọi ticket do agent đề xuất đều có bản xem trước và nút xác nhận. Quy tắc này áp dụng cả khi người dùng gõ “tạo ticket”.
- Triển khai local bằng Docker Compose là điều kiện hoàn thành. Public hosting là tùy chọn sau V1.

### 1.3. Kết quả cần chứng minh

Một nhân viên hỏi về lỗi IT, nhận hướng dẫn có nguồn, kiểm tra trạng thái dịch vụ, xem ticket của mình và tạo ticket sau xác nhận. Ở cuộc trò chuyện mới, agent sử dụng thông tin thiết bị đã được người dùng đồng ý lưu.

Bộ bàn giao gồm source code, dữ liệu seed, migrations, automated tests, báo cáo evaluation, hướng dẫn chạy và video demo. Các nhãn “resolved”, “ticket created” phải dựa trên bằng chứng tương ứng.

## 2. Phạm vi và các mốc sản phẩm

| Năng lực | Demo sớm, kết thúc M2 | V1 hoàn chỉnh, kết thúc M7 |
|---|---|---|
| Đăng nhập, kiểm tra quyền | Có | Có, kèm negative tests |
| Web chat và lịch sử | Có | Có, reconnect và trạng thái xử lý |
| RAG và nguồn tham khảo | Có, dữ liệu seed | Hybrid retrieval, versioning, upload PDF/Markdown |
| LangGraph | Graph hỏi/tra cứu/trả lời | Graph có tools, checkpoint, approval, recovery |
| MCP | Chưa là điều kiện demo sớm | Một server, ba business tools chạy qua MCP |
| Ticket | Chưa là điều kiện demo sớm | Xem/tạo/cập nhật trạng thái bởi IT, chống tạo trùng |
| Memory qua cuộc trò chuyện | Chưa là điều kiện demo sớm | Fact có cấu trúc và lịch sử sự cố có kiểm soát |
| Redis | Queue và rate limit | Thêm embedding cache có TTL |
| Langfuse | Trace đầu tiên | Trace end-to-end, token/cost, feedback liên kết |
| Evaluation | Dataset và baseline đầu tiên | Bộ regression, benchmark và báo cáo kết quả |

V1 chỉ hoàn thành khi có đủ các thành phần người xây dựng yêu cầu. Mốc demo sớm giúp kiểm tra sản phẩm trước khi hoàn thiện toàn bộ.

Ngoài phạm vi V1:

- Reset password, disable account, chạy shell, cài phần mềm hoặc sửa cấu hình máy thật.
- Jira/ServiceNow/SSO/Teams/Slack thật, public MCP endpoint.
- Multi-agent, microservices tách domain, Kubernetes, Kafka.
- Fine-tuning, vLLM, GPU, quantization, model routing tự động.
- OCR, PDF scan, ảnh trong chat, voice, crawl website tự động.
- Billing, quản trị nhiều công ty, SLA cho khách hàng trả tiền.
- Answer cache và vector memory tự do.

## 3. Người dùng, quyền và quy tắc nghiệp vụ

### 3.1. Vai trò

| Thao tác | Employee | IT staff | Admin |
|---|---|---|---|
| Chat, xem conversation và memory của mình | Có | Có | Có |
| Xem tài liệu công khai trong công ty | Có | Có | Có |
| Xem tài liệu giới hạn phòng ban | Đúng phòng ban | Đúng phòng ban | Tất cả |
| Xem tài liệu chỉ dành cho IT | Không | Có | Có |
| Xem ticket của mình | Có | Có | Có |
| Xem/cập nhật ticket qua trang IT | Không | Ticket thuộc phòng ban mình | Tất cả |
| Xác nhận ticket do agent tạo cho mình | Có | Có | Có |
| Upload/publish/archive tài liệu | Không | Không | Có |
| Đổi trạng thái dịch vụ mô phỏng | Không | Không | Có |

Role không mặc nhiên cho phép đọc conversation hoặc memory riêng của người khác, kể cả admin. Agent chỉ có tool xem ticket của người đang đăng nhập; giao diện IT sử dụng API riêng có scope phù hợp.

### 3.2. Quy tắc hỗ trợ IT

- Hỏi thông tin còn thiếu: thiết bị nào, OS/version, thông báo lỗi, thời điểm xảy ra.
- Trạng thái registry “healthy” chỉ nói về dịch vụ; không chứng minh kết nối từ máy người dùng bình thường.
- Chỉ đánh dấu bước “đã thử” khi người dùng xác nhận; lưu riêng bước “đã đề xuất”.
- Chỉ đánh dấu vấn đề “resolved” sau xác nhận của người dùng hoặc IT cập nhật ticket resolved.
- Nếu không có tài liệu phù hợp, nói rõ thiếu căn cứ, hỏi thêm hoặc đề xuất ticket.
- Tài liệu công khai không có thẩm quyền xác định hostname, CA, quyền truy cập hay chính sách công ty giả lập.
- Người dùng có thể yêu cầu ticket ngay. Không ép họ thử đủ số bước.
- Khi vẫn lỗi sau hai bước phù hợp đã được xác nhận, đề xuất chuyển IT; đây là policy khởi đầu có cấu hình.
- Ticket severity là `low | normal | high`; `high` cần mô tả tác động, hiển thị trong preview.
- Trước khi tạo, hiển thị ticket đang mở của chính người dùng cùng nhóm vấn đề. Không tự gộp chỉ vì tiêu đề giống nhau.
- Không xem “đã tạo ticket” là “đã giải quyết lỗi”.

## 4. Các luồng phải chạy được

| ID | Tình huống | Hành vi và điều kiện chấp nhận |
|---|---|---|
| UC-01 | “Cài VPN trên Ubuntu thế nào?” | Tìm tài liệu đang có hiệu lực, trả lời có source/page/section hợp lệ |
| UC-02 | “VPN đang down à?” | Gọi status tool, nêu trạng thái và thời điểm kiểm tra |
| UC-03 | “Docker báo lỗi chứng chỉ” | Hỏi thiết bị nếu chưa rõ, tìm runbook, ghi nhận các bước đã thử |
| UC-04 | “Vẫn lỗi, tạo ticket giúp tôi” | Preview → xác nhận → đúng một ticket → hiển thị ID từ DB |
| UC-05 | “Tôi đang có ticket nào?” | Chỉ trả ticket của current user |
| UC-06 | Sang conversation mới: “Máy hôm trước lại lỗi” | Dùng memory đã xác nhận; hỏi lại khi nhiều thiết bị/sự cố phù hợp |
| UC-07 | Xin ticket hoặc tài liệu trái quyền | Không trả nội dung, tiêu đề hay snippet của đối tượng không được phép |
| UC-08 | Admin upload phiên bản tài liệu mới | Ingest xong mới publish; bản cũ không còn là nguồn cho câu trả lời mới |
| UC-09 | Refresh khi chờ approval; bấm approve hai lần | Khôi phục preview; không mất action, không tạo trùng |
| UC-10 | Model/tool/Redis bị lỗi | UI báo trạng thái rõ; dữ liệu đã commit vẫn truy vấn được |
| UC-11 | Tắt hoặc xóa memory | Lượt mới không dùng memory đã tắt/xóa; job cũ không tự lưu lại |
| UC-12 | IT cập nhật ticket resolved | Lịch sử sự cố dùng trạng thái mới, không tiếp tục coi ticket là open |

Kịch bản trình diễn chính: Docker certificate trên Ubuntu → hướng dẫn có citation → vẫn lỗi → xác nhận ticket → IT xử lý → conversation mới nhận ra sự cố trước đó.

## 5. Kiến trúc và stack

### 5.1. Stack đã chọn

| Lớp | Công nghệ | Vai trò cụ thể |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | HTTP API, validation, orchestration boundary |
| Database | PostgreSQL 17, pgvector | Business data, retrieval, checkpoint |
| DB access | SQLAlchemy 2.x, psycopg 3, Alembic | Queries, transaction, migrations |
| Agent | LangGraph + PostgreSQL checkpointer | Graph, checkpoint, pause/resume |
| LLM | OpenAI Python SDK, Responses API | Function calling và structured output |
| Embedding | OpenAI embeddings API | Một embedding space thống nhất |
| Tools | Official MCP Python SDK | Một server stdio cho status/ticket |
| Jobs | Celery + Redis | Agent execution, ingestion, memory jobs |
| Scheduler | Celery beat | Reconcile queued jobs, cleanup/retention |
| Cache/rate limit | redis-py | Atomic rate limit và embedding cache |
| PDF | pypdf | Text PDF có thể trích xuất |
| Frontend | React, TypeScript, Vite, React Router, TanStack Query | Chat, ticket, tài liệu, memory settings |
| Styling | Tailwind CSS | Giao diện đơn giản, responsive |
| Observability | Structured JSON logs + Langfuse Python SDK | Trace/cost/feedback |
| Tests | pytest, HTTPX, Playwright | Unit, integration, web E2E |
| Tooling | uv, Ruff, mypy, npm, ESLint | Dependency lock và kiểm tra code |
| Deployment | Docker Compose | Chạy và seed local tái lập được |

Các major version nêu trên là quyết định tương thích ban đầu. M0 khóa patch versions đã smoke-test trong `uv.lock` và `package-lock.json`, pin Docker image/digest. Không dùng tag `latest` làm cơ sở benchmark.

MCP SDK hiện có thay đổi giữa major versions; đọc đúng docs của phiên bản được khóa. Không trộn ví dụ FastMCP của SDK cũ với API mới. [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).

### 5.2. Sơ đồ triển khai V1

```mermaid
flowchart TD
    UI["React web"] --> API["FastAPI: auth, API, SSE"]
    API --> PG["PostgreSQL + pgvector"]
    API --> REDIS["Redis: queue, rate limit, cache"]
    REDIS --> AW["Agent worker: LangGraph"]
    REDIS --> BW["Background worker: ingestion, memory"]
    BEAT["Celery beat"] --> REDIS
    AW --> PG
    BW --> PG
    AW --> LLM["OpenAI API"]
    BW --> LLM
    AW --> MCP["MCP server: stdio subprocess"]
    MCP --> PG
    API --> LF["Langfuse Cloud"]
    AW --> LF
    BW --> LF
```

- API, workers và MCP server là các entrypoint của cùng package Python; chia tiến trình theo công việc.
- MCP server chạy như subprocess của agent job, không có cổng public.
- `search_knowledge_base` gọi RAG trong worker. Ba tool nghiệp vụ còn lại đi qua MCP.
- MCP server dùng service/repository cùng codebase để thao tác ticket và đọc trạng thái giả lập.
- Chỉ API phục vụ browser. Không đưa OpenAI/Langfuse secret key vào frontend.
- File tài liệu nằm trên volume chia sẻ API/background worker; download qua API có kiểm tra quyền.
- Agent worker không trực tiếp sửa ticket. Mọi write của agent đi qua executor và ticket service trong MCP server.

### 5.3. Nguyên tắc mô-đun

Router không chứa prompt hay truy vấn vector. Graph không chứa HTTP-specific logic. MCP chỉ là adapter gọi business service; quyền và transaction vẫn được kiểm tra ở service. Model provider chỉ biết yêu cầu sinh output, tool schema và usage.

Giới hạn bốn abstractions chính: model provider, retriever, tool executor, repositories/services theo domain. Không tạo interface rỗng cho mọi class.

## 6. Dữ liệu demo và tài liệu đầu vào

### 6.1. Bộ seed bắt buộc

- Công ty giả lập `Acme IT Lab`; các domain minh họa dùng `.example`.
- Hai phòng ban Engineering và Operations.
- Sáu account: hai employee Engineering, một employee Operations, một IT staff mỗi phòng ban, một admin.
- Mỗi tài khoản có email giả; password seed nhận qua biến môi trường và chỉ bật ở demo mode.
- 20 tài liệu gốc tự viết: runbook VPN, registry/CA, GitLab, cài đặt, escalation, chính sách hỗ trợ.
- Có tài liệu company-wide, department-only, IT-only và ít nhất hai phiên bản của ba tài liệu.
- Khoảng 20 ticket ở các trạng thái open/in_progress/resolved.
- Ba dịch vụ: `vpn`, `registry`, `gitlab`; preset healthy/degraded/down/unknown.
- Ít nhất ba PDF text tự tạo từ nội dung do dự án sở hữu; còn lại Markdown với metadata.
- Tình huống độc hại chỉ nằm trong test fixtures có nhãn rõ, không publish vào corpus demo mặc định.

Seed có ID ổn định, idempotent, không xóa dữ liệu người dùng tự thêm. Reset demo là lệnh riêng với confirmation, giới hạn đúng database demo.

### 6.2. PDF tải trên mạng

V1 không phụ thuộc vào việc tải một PDF bên ngoài mới chạy được. Nếu bổ sung PDF công khai, manifest phải ghi `source_url`, tác giả/đơn vị, ngày tải, checksum, điều kiện sử dụng và `authority=public_reference`.

Chỉ đưa file vào repository khi có quyền phân phối phù hợp; nếu chưa rõ, lưu manifest và hướng dẫn tải. Admin upload file local, không nhập URL để backend tự fetch. Điều này cũng giới hạn phạm vi crawler và URL handling.

### 6.3. Hợp đồng tài liệu

`Document` là định danh logic; `DocumentVersion` là một lần xuất bản; `DocumentChunk` thuộc chính xác một version.

Metadata bắt buộc:

```json
{
  "document_key": "docker-registry-ubuntu",
  "title": "Docker registry trên Ubuntu",
  "version_label": "2.0",
  "authority": "internal_policy",
  "visibility": "company",
  "department_id": null,
  "language": "vi",
  "effective_at": "2026-01-01T00:00:00Z",
  "expires_at": null,
  "source_url": null
}
```

`visibility = company | department | it_only`. Khi visibility là department phải có department_id; các trường hợp khác department_id phải null. Không dùng một metadata department mơ hồ đồng thời làm “đơn vị biên soạn” và “quyền đọc”.

## 7. Giao diện web

| Route | Màn hình | Hành vi chính |
|---|---|---|
| `/login` | Đăng nhập | Account seed, lỗi đăng nhập chung, thông tin demo |
| `/chat`, `/chat/:id` | Chat | Sidebar lịch sử, tin nhắn, trạng thái, citation, preview approval |
| `/tickets`, `/tickets/:id` | Ticket của tôi | Trạng thái, mô tả, nguồn conversation, thời gian cập nhật |
| `/it/tickets` | Hàng đợi IT | Ticket đúng scope; đổi trạng thái và thêm resolution note |
| `/admin/documents` | Quản lý knowledge | Upload, tiến độ, phiên bản, publish/archive, preview text |
| `/admin/services` | Mô phỏng dịch vụ | Chọn status và tình huống timeout cho demo |
| `/settings/memory` | Memory | Bật/tắt, xem nguồn, duyệt đề xuất, sửa/xóa |

Chat hiển thị sự kiện như “Đang tra tài liệu”, “Đang kiểm tra VPN”, “Cần bạn xác nhận”. Không hiển thị hidden reasoning, raw prompt, raw checkpoint hoặc internal tool payload.

Bản trả lời được buffer và kiểm tra trước khi phát tới UI. V1 stream trạng thái workflow qua SSE, chưa stream token câu trả lời chưa kiểm tra. Có skeleton/loading, lỗi có retry, empty state và bố cục dùng được trên màn hình nhỏ.

Nút xác nhận hiển thị title, description, issue_type, severity, thiết bị, người tạo và hạn xác nhận. Nút sửa tạo draft mới; nút hủy từ chối draft hiện tại. Browser không tự suy ra ticket đã tạo từ nội dung model.

## 8. Ingestion và RAG

### 8.1. Upload và xuất bản

1. Admin upload PDF text hoặc Markdown, kèm metadata. Giới hạn khởi đầu: 10 MB, 100 trang, tối đa 1 MB text sau parse.
2. API kiểm tra quyền, extension/MIME/signature, kích thước và checksum; lưu file bằng storage key do server sinh.
3. Tạo document/version ở trạng thái `draft` và ingestion job; trả `202 + job_id`.
4. Background worker parse, giữ page number/heading; loại header/footer lặp và chuẩn hóa whitespace vừa đủ.
5. PDF scan, file mã hóa hoặc parse không ra text: job failed với lý do cụ thể. Parser có timeout và chạy trong subprocess bị giới hạn tài nguyên.
6. Chunk theo heading/paragraph, khởi đầu 400–600 token, hard cap 800 token; overlap tối đa 80 token khi phải chia một đoạn dài.
7. Giữ code block cùng hướng dẫn liên quan; block quá lớn được chia có nhãn continuation, không được lặng lẽ cắt mất lệnh.
8. Embed theo batch nhỏ, lưu chunk và embedding của version draft; retry dựa trên content hash và embedding version.
9. Đánh dấu version `ready` khi tất cả chunk hợp lệ. Admin xem preview rồi publish.
10. Publish trong một transaction: đổi `documents.current_version_id`, đánh dấu bản cũ superseded và tăng corpus revision. Mỗi document có đúng một current version.

Job ingest thất bại không thay bản đang phục vụ. Publish từ chối version chưa ready hoặc effective_at ở tương lai; có thể chuẩn bị draft trước và publish sau. Archive làm tài liệu ngừng xuất hiện trong lượt tìm kiếm mới.

Lưu file gốc, extracted text và metadata provenance. Dọn file upload mồ côi theo retention job. Giới hạn file/page là quyết định cho V1; pypdf không làm OCR và PDF phức tạp cần kiểm tra chất lượng trích xuất riêng. [pypdf: Extract Text](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

### 8.2. Retrieval có phân quyền

```text
User query + authenticated principal
→ xác định scope và current versions có hiệu lực
→ query embedding
→ vector top 20 + lexical top 20, cả hai đều có SQL permission filters
→ deduplicate + Reciprocal Rank Fusion
→ top 5 trong giới hạn context
→ kiểm tra lại quyền/hiệu lực trước khi tạo câu trả lời
→ trả citation gắn với version/chunk thực tế
```

- Query filter bắt buộc: visibility/department/role, current_version_id, archived=false, effective_at và expires_at.
- Bộ lọc được server tạo; tool chỉ nhận query, không nhận SQL/filter hoặc department do LLM chọn.
- Dùng cosine exact search cho corpus nhỏ và PostgreSQL FTS `ts_rank_cd`; GIN index cho lexical search.
- Giữ error codes và tên sản phẩm trong trường lexical riêng; test token hóa cho tiếng Việt và chuỗi như `x509`, `ERR_CERT_AUTHORITY_INVALID`.
- Fuse theo rank: `RRF(d) = sum(1 / (60 + rank_i(d)))`; không cộng trực tiếp cosine score và lexical score.
- Với corpus V1, khởi đầu bằng exact vector search. Chỉ thêm HNSW khi đo thấy cần; kiểm tra filtered recall và iterative scan khi chuyển sang ANN.
- SQL WHERE là ranh giới quyền. Với HNSW, PostgreSQL có thể lọc sau khi scan index về mặt thực thi; không nhầm điều này với lấy top-k trái quyền về ứng dụng rồi mới lọc.
- Reranker tắt mặc định. Chỉ thêm sau baseline nếu cải thiện chất lượng đủ bù latency và chi phí.
- Không dùng một ngưỡng cosine tùy ý để khẳng định câu trả lời chắc chắn đúng.

pgvector có hướng dẫn về filtering, exact/approximate search và hybrid fusion; PostgreSQL FTS dùng ranking riêng, không được đặt tên là BM25 trong báo cáo. [pgvector](https://github.com/pgvector/pgvector), [PostgreSQL text search](https://www.postgresql.org/docs/current/textsearch-controls.html).

### 8.3. Citation và câu hỏi không đủ căn cứ

Source do retriever tạo gồm `source_id, document_id, version_id, chunk_id, title, page_number, section, excerpt`. Markdown không có trang thì page_number=null. Trang PDF dùng số trang vật lý bắt đầu từ 1.

Model chỉ được tham chiếu source_id đã có trong context. Backend kiểm tra ID, quyền và version; citation sai làm câu trả lời bị sửa một lần trong budget, rồi trả thông báo thiếu căn cứ nếu vẫn lỗi. Kiểm tra ID không tự chứng minh mọi claim được source hỗ trợ; mức hỗ trợ nội dung còn được đánh giá trong evaluation.

Nếu không có đoạn đủ hỗ trợ: trả outcome `needs_input` hoặc `escalation_offered`. Không tự suy diễn chính sách nội bộ từ kiến thức model. Chỉ dùng source_url do ingestion kiểm soát, không render link hoặc ảnh tùy ý do model tạo.

## 9. Agent runtime và LangGraph

### 9.1. Đơn vị thực thi

- Conversation là cuộc trò chuyện; mỗi tin nhắn người dùng tạo một `agent_run`.
- `thread_id` của LangGraph bằng run_id do backend sinh, không do browser cung cấp.
- Một run có thể pause chờ approval và tiếp tục với cùng thread_id. Tin nhắn thông thường tiếp theo tạo run mới, nạp context của conversation từ DB.
- Một conversation chỉ có một run chưa kết thúc, kể cả khi đang chờ approval. UI yêu cầu xử lý/hủy draft trước khi gửi tin mới.
- `ask_user` kết thúc lượt với outcome needs_input; không giữ job chạy trong lúc người dùng suy nghĩ.
- Checkpoint lưu bằng PostgreSQL checkpointer; approval/ticket vẫn là business records riêng.

Run status: `queued | running | waiting_approval | resume_queued | completed | failed | cancelled`. Outcome là kết quả nghiệp vụ, tách khỏi status: answered, needs_input, resolved, escalation_offered, ticket_created, approval_rejected, approval_expired hoặc error.

Run có `kind=chat | manual_ticket`. Khi model không sẵn sàng, form thủ công tạo manual_ticket run và đi thẳng vào node draft/approval; không cần model call. Quyền và cơ chế tạo ticket giống chat run.

### 9.2. Graph

```mermaid
flowchart TD
    START --> Load["Load context + current permissions"]
    Load -->|chat| Decide["LLM: tool call hoặc final answer"]
    Load -->|manual ticket| Draft
    Decide -->|read tool| Validate["Validate schema + authorize"]
    Validate --> Read["Execute local RAG / MCP read"]
    Read --> Decide
    Decide -->|create_ticket| Draft["Validate + persist ticket draft"]
    Draft --> Pause["interrupt: waiting_approval"]
    Pause -->|approve| Check["Recheck actor, hash, expiry, permission"]
    Check --> Write["MCP create_ticket: atomic + idempotent"]
    Write --> Receipt["Receipt từ kết quả DB"]
    Pause -->|reject / expire| Closed["Không tạo ticket"]
    Decide -->|answer / ask user| Output["Validate answer + citations"]
    Receipt --> Finish["Persist message, outcome, events"]
    Closed --> Finish
    Output --> Finish
    Finish --> MemoryJob["Schedule memory extraction nếu đã bật"]
    MemoryJob --> END
```

Mọi nhánh tool đều kiểm tra quyền trước execution; MCP/business service kiểm tra lại. Không gọi external system trước permission/approval.

### 9.3. State tối thiểu

```text
run_id, conversation_id, actor_id, schema_version
input_message_id, issue_type, selected_device_id
recent_message_ids, summary_version
suggested_steps[], confirmed_attempted_steps[]
retrieved_source_ids[], retrieved_memory_ids[]
model_items[], tool_call_ids[]
pending_approval_id, ticket_id
decision_count, tool_count, input_tokens_total, output_tokens_total
active_deadline, outcome, last_error
```

Chỉ lưu dữ liệu serializable; không lưu DB session/client/secret trong state. State có thể chứa untrusted tool text nhưng không trở thành nguồn cấp quyền.

### 9.4. Giới hạn ban đầu

| Giới hạn | Giá trị |
|---|---|
| Model calls cho một run | Tối đa 4, gồm repair calls; memory job có budget riêng |
| Tool executions | Tối đa 4 read calls và 1 ticket write đã xác nhận |
| Tool call trùng query/arguments | Reuse kết quả còn mới; tối đa 1 lần lặp |
| Graph recursion limit | 24 transitions, thêm application counters ở từng node |
| Active execution deadline | 60 giây cho mỗi đoạn chạy, không tính thời gian chờ approval |
| Chờ approval | 15 phút kể từ lúc tạo draft |
| Model call timeout | 20 giây/lần, còn chịu deadline tổng |
| Read tool timeout | 5 giây, tối đa 1 retry lỗi tạm thời |
| Final output | Tối đa 1.500 token/call, cộng vào run budget |

Khi hết budget: kết thúc có trạng thái rõ, đề xuất chuyển IT; không mở một vòng agent mới vô hạn. Đường xác nhận ticket trả receipt bằng template từ DB để không phụ thuộc thêm một model call.

LangGraph resume có thể chạy lại node chứa interrupt. Tách việc tạo draft idempotent, node chờ và node write; không thực thi tạo ticket trước interrupt. [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence).

## 10. Tool contract và MCP

### 10.1. Bốn tool model nhìn thấy

| Tool | Arguments do model được phép tạo | Execution |
|---|---|---|
| `search_knowledge_base` | `query: string[1..1000]` | RAG local trong agent worker |
| `check_service_status` | `service: vpn \| registry \| gitlab` | MCP read |
| `get_my_open_tickets` | Không có | MCP read, tối đa 10 ticket mới nhất |
| `create_ticket` | `title, description, issue_type, severity, device_id` | Propose → approval → MCP write |

Title dài 5–160 ký tự; description 10–4.000 ký tự; issue_type là vpn/docker/gitlab/other; device_id nullable và phải thuộc actor. Nullable fields vẫn khai báo rõ trong strict schema.

Tool arguments tuyệt đối không chứa user_id, role, department, SQL, URL đích, token, approval flag hoặc idempotency key do model tự chọn. Pydantic dùng `extra="forbid"`; backend kiểm tra business rules ngoài JSON schema.

`create_ticket` trong tool registry là khả năng đề xuất tạo ticket. Chỉ executor sau approval mới gọi method tạo ticket thực sự trên MCP server.

### 10.2. Kết quả tool

```json
{
  "status": "success",
  "data": {
    "service": "vpn",
    "service_status": "degraded",
    "checked_at": "2026-09-15T08:00:00Z",
    "source": "simulated_monitor"
  },
  "error": null
}
```

Envelope chung: `status = success | failed | unknown`, `data` nullable, `error = {code, retryable, safe_message}` nullable. “unknown” nghĩa là chưa xác nhận được kết quả, không phải success.

Ticket result có ticket_id, display_key, status, created_at. Chỉ receipt này hoặc truy vấn lại DB mới cho phép UI báo tạo thành công. Nội dung mô tả ticket/tool result vẫn là dữ liệu không đáng tin, phải giới hạn chiều dài và lọc secret.

### 10.3. MCP V1

- Một server `it_helpdesk` với ba business tools; dùng official Python SDK, transport stdio.
- Mỗi execution segment của agent job tạo subprocess riêng; khởi động bằng module cố định, không có shell command do user/model cung cấp.
- Actor/run được worker tra DB và truyền qua environment allowlist khi tạo subprocess. Đây là context tin cậy của ứng dụng, không nằm trong tool schema.
- Server đối chiếu actor với run trong DB, đọc quyền hiện tại và kiểm tra quyền mỗi call; cấm dùng global actor chia sẻ giữa nhiều user.
- Write call nhận approval_id qua metadata do executor bổ sung; server tra và xác minh record đã approved, arguments hash, owner và expiry.
- Chỉ subprocess do ứng dụng kiểm soát được dùng cấu hình này. Không mô tả nó là authentication cho MCP public.
- MCP subprocess chỉ nhận DB/service configuration cần thiết; không thừa hưởng OpenAI/Langfuse keys.
- Stdout chỉ dành cho giao thức MCP; logs ra stderr và được redact.
- Discovery chỉ lấy ba tên/schema allowlist đã pin; schema thay đổi làm startup/contract test thất bại.
- Trace nối qua run_id/trace_id do worker tạo. Kết thúc segment phải đóng client và thu hồi subprocess.

Stdio là transport chuẩn cho client khởi chạy server local. Chuyển sang Streamable HTTP/OAuth là ADR riêng sau V1. [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).

## 11. Approval, ticket và tính nhất quán

### 11.1. Approval workflow

1. Model đề xuất ticket. Backend canonicalize và validate arguments, kiểm tra device ownership.
2. Tạo approval record với action_id ổn định theo run/tool-call; lưu canonical_args, arguments_hash, expires_at, version.
3. Sau khi checkpoint đã pause, UI đọc draft từ DB và hiển thị preview.
4. Người dùng bấm approve; API xác minh session, owner, version và expiry bằng transaction.
5. API chuyển pending → approved, run → resume_queued; enqueue resume job. Nội dung draft được khóa từ đây.
6. Resume payload của LangGraph do worker dựng từ record DB; browser không được gửi `Command(resume=...)` tùy ý.
7. Executor gọi MCP với đúng canonical_args đã được duyệt.
8. MCP server recheck và tạo ticket + cập nhật approval executed + audit event trong cùng DB transaction.
9. Worker lưu receipt/message/event. Nếu graph bị ngắt sau commit, retry dùng approval_id lấy ticket cũ.

```text
pending → approved → executed
pending → rejected
pending / approved chưa execute → expired
```

Approval không nâng quyền: user có thể approve nhưng action vẫn bị từ chối nếu tài khoản đã bị vô hiệu hóa hoặc quyền đã đổi. Một approval chỉ được dùng cho một action.

“Sửa” trên UI thực hiện hủy draft cũ rồi gửi mô tả đã sửa để tạo run/draft mới. Không đổi arguments sau khi người dùng đã xác nhận. Repeated approve cùng version trả cùng trạng thái; approve sau reject/expiry trả conflict hoặc expired.

### 11.2. Idempotency và concurrency

- Tạo run: unique `(actor_id, client_request_id)`; request lặp cùng payload trả run cũ, khác payload trả 409.
- Draft: unique `action_id`; retry node propose không tạo approval thứ hai.
- Ticket: unique `approval_id`; chính DB constraint bảo vệ chống double-click và job delivery trùng.
- Nếu receipt đã tồn tại, replay đúng owner/arguments trả ticket cũ kể cả thời hạn approve ban đầu đã qua. Expiry chỉ chặn write chưa commit, không che giấu một write đã thành công.
- Quyết định approval và ticket write dùng row lock/conditional update; không giữ transaction mở qua model call hoặc lúc chờ người dùng.
- Mỗi run chỉ một executor; dùng PostgreSQL advisory lock trên connection riêng suốt segment và owner/lease của run để phát hiện worker chết.
- Khi mất connection giữ lock, worker dừng segment; service kiểm tra execution ownership trước side effect. M0/M4 phải test đường recovery này.
- Checkpoint và business transaction không atomic với nhau. Vì vậy checkpoint replay phải đọc receipt/action record trước khi chạy lại write.
- SSE reconnect chỉ đọc lại events; không enqueue lại job.

Trong V1, ticket và approval nằm cùng PostgreSQL nên atomic write đạt được bằng một transaction. Khi thay bằng Jira/ServiceNow cần thiết kế outbox/reconciliation riêng; local idempotency key không tự đảm bảo hệ thống bên ngoài không tạo trùng.

### 11.3. Vòng đời ticket

`open → in_progress → resolved`; resolved có thể reopen về open bằng IT staff đúng scope/admin. Cập nhật yêu cầu version hiện tại; 409 nếu người khác vừa sửa. Resolved cần resolution_note.

Agent không có tool đóng/xóa ticket. Nhân viên xác nhận “đã hết lỗi” làm conversation outcome resolved; ticket còn mở vẫn do IT xử lý, tránh tự động thay đổi workflow IT.

## 12. Memory và context

### 12.1. Hai loại memory V1

**Fact có cấu trúc:** thông tin OS, OS version, device label và preferred language. Fact hệ điều hành gắn với device_id, không gắn duy nhất với user vì một người có thể có nhiều máy.

**Lịch sử sự cố:** issue_type, device_id, ticket_id và kết quả đã xác nhận. Ticket status/resolution được đọc từ DB hiện tại; không tin một câu summary cũ về trạng thái ticket.

V1 dùng structured lookup theo owner/device/issue_type và lịch sử gần nhất, không cần vector memory. Tối đa năm fact và ba sự cố liên quan được đưa vào context.

### 12.2. Ghi nhớ

- Mặc định off; người dùng bật trong settings. Chat vẫn hoạt động khi tắt.
- Sau lượt chat, background job chỉ xem các phát biểu của người dùng thuộc schema allowlist để đề xuất fact.
- Candidate có source_message_id, device_id, key, value, observed_at, extractor_version và memory_epoch.
- Fact từ model extraction ở trạng thái pending; UI cho xác nhận trước khi active. Người dùng sửa thủ công cũng là confirmed.
- Episodic memory được tạo từ sự kiện có cấu trúc như ticket_created/resolved và bước user xác nhận, không suy diễn cách giải quyết đã thành công.
- Fact mới cho cùng user/device/key tạo revision và inactive bản trước; cập nhật khác thiết bị không ghi đè nhau.
- Memory không chứa role, permission, lệnh “lần sau bỏ kiểm tra” hoặc secret. Memory không trở thành system instruction.
- Fact active hết hạn sau 90 ngày nếu chưa xác nhận lại; incident lookup mặc định trong 90 ngày.
- Job deduplicate theo user/source_message/extractor_version; job lỗi không làm chat thất bại.

### 12.3. Tắt, sửa, xóa

Memory settings có counter `memory_epoch`. Khi tắt/xóa, tăng counter; worker phải so sánh lại trước khi commit để job cũ không tái tạo dữ liệu vừa bị xóa. Candidate pending từ epoch cũ không được accept; active facts còn giữ được không tự mất chỉ vì epoch tăng.

Mỗi run tải lại memory active đã được xác nhận và đúng owner, đọc settings/epoch hiện tại để phát hiện thay đổi trong lúc build context. Epoch kiểm soát job/race, không phải điều kiện loại bỏ mọi active fact cũ. Tắt memory ngừng sử dụng và ghi mới; bật lại dùng các active fact chưa xóa/chưa hết hạn. Xóa một mục không xóa các mục khác.

Không hồi sinh memory từ checkpoint của run cũ. UI phân biệt “xóa mục ghi nhớ” với “xóa lịch sử chat”; xóa memory không xóa phát biểu gốc trong conversation hiện tại. Extraction chỉ xử lý source messages mới của run, không quét lại toàn bộ history.

Khi dùng lịch sử sự cố từ các conversation khác, luôn kiểm tra memory enabled và chỉ bắt đầu từ episodic records còn active rồi mới lấy ticket status hiện tại. Không quét tất cả ticket cũ để tự dựng lại memory đã xóa. Ticket resolved event chỉ cập nhật memory sự cố còn tồn tại; không tự tạo lại mục đã xóa. Người dùng vẫn xem được ticket của mình qua ticket tool/UI.

### 12.4. Context budget

Budget khởi đầu tối đa 10.000 input tokens/call, bao gồm tool schemas:

| Thành phần | Ngân sách tối đa |
|---|---|
| System/developer instruction và tool schemas | 2.000 |
| Recent messages + structured issue summary | 2.500 |
| Memory | 500 |
| RAG chunks | 3.000 |
| Tool results | 1.000 |
| Dự phòng formatting/input | 1.000 |

Đây là ceiling, không phải phải lấp đầy. Giữ câu hỏi hiện tại, tool-call/result pairs và confirmed_attempted_steps; bỏ evidence dư trước. Tối đa 40.000 input và 6.000 output tokens cộng dồn/run.

Chỉ compact khi history vượt ngân sách: ưu tiên summary từ structured issue state, chỉ dùng model summary khi cần và có nguồn message IDs. Không biến “agent đề xuất” thành “user đã thử”.

Source quyền đọc bị thu hồi phải được loại khỏi cả retrieval và history/context. Messages có nội dung dựa trên source nay trái quyền được ẩn nội dung và thay placeholder khi đọc lại; model không nhận đoạn văn cũ đó. Source cũ đã superseded nhưng vẫn được phép đọc chỉ xuất hiện như lịch sử, không làm hướng dẫn hiện hành.

## 13. Database và ownership

### 13.1. Quy ước

UUID cho internal ID, UTC cho timestamps, display_key riêng cho ticket. Bảng thay đổi qua UI có integer version để optimistic concurrency. JSONB dành cho payload/state linh hoạt; owner/status/version/filterable fields dùng cột có kiểu.

Single-company V1 không cần organizations/memberships/billing. Phân quyền tài liệu dựa trên visibility, department và role. Nếu thêm multi-tenant sau này phải bổ sung tenant isolation vào toàn bộ query, cache, job và test suite trước khi phục vụ nhiều công ty.

### 13.2. Schema nghiệp vụ tối thiểu

| Bảng | Cột chính và ràng buộc |
|---|---|
| `departments` | id, name unique |
| `users` | id, email unique, password_hash, role, department_id FK, active, memory_enabled, memory_epoch |
| `sessions` | id, token_hash unique, user_id FK, csrf_token_hash, created_at, expires_at, revoked_at |
| `devices` | id, owner_id FK, label, active; nhãn không được dùng thay ownership |
| `conversations` | id, owner_id FK, title, selected_device_id FK nullable, issue_state JSONB, version, created_at, updated_at |
| `messages` | id, conversation_id FK, run_id FK nullable, role, content, outcome nullable, created_at |
| `message_sources` | message_id FK, chunk_id FK; unique pair để kiểm tra citation và quyền đọc lại |
| `agent_runs` | id, conversation_id FK, actor_id FK, kind, client_request_id, input_hash, status, outcome, checkpoint_thread_id, prompt_version, model, counters, attempts, version, lease_owner, lease_until, execution_version, error_code, created_at, finished_at |
| `run_events` | id, run_id FK, sequence, type, safe_payload JSONB, created_at; unique(run_id, sequence) |
| `tool_calls` | id, run_id FK, model_call_id, tool_name, arguments_hash, safe_arguments, result_status, safe_result, duration_ms, attempt |
| `approval_requests` | id, action_id unique, run_id FK, owner_id FK, tool_name, canonical_args, arguments_hash, status, version, expires_at, approved_by FK nullable, approved_at, executed_at |
| `tickets` | id, display_key unique, owner_id FK, department_id FK, device_id FK nullable, conversation_id FK, approval_id FK unique, title, description, issue_type, severity, status, resolution_note nullable, version, created_at, updated_at |
| `ticket_events` | id, ticket_id FK, actor_id FK, event_type, from_status, to_status, note, created_at |
| `service_states` | service_id PK, status, fault_mode, updated_by FK, updated_at; chỉ ba service IDs allowlist |
| `system_state` | singleton id, corpus_revision; tăng trong transaction publish/archive/ACL change |
| `documents` | id, document_key unique, title, visibility, department_id FK nullable, archived, current_version_id FK nullable, access_version, version |
| `document_versions` | id, document_id FK, version_label, status, authority, language, source_url, source_checksum, storage_key, effective_at, expires_at, parser_version, chunker_version, embedding_model, embedding_dimensions, created_at |
| `document_chunks` | id, version_id FK, ordinal, page_number nullable, section nullable, content, token_count, content_hash, lexical_text, search_vector, embedding vector(1536); unique(version_id, ordinal) |
| `ingestion_jobs` | id, document_version_id FK, status, stage, progress, attempts, lease_until, error_code, created_at, completed_at |
| `memories` | id, owner_id FK, device_id FK nullable, scope_key, memory_type, fact_key nullable, value JSONB, ticket_id FK nullable, source_message_id FK nullable, status, memory_epoch, extractor_version, confirmed_at, observed_at, expires_at, version |
| `memory_jobs` | id, owner_id FK, source_run_id FK, memory_epoch, extractor_version, status, attempts, lease_until, error_code |
| `feedback` | id, owner_id FK, message_id FK, rating, reason nullable, created_at; unique(owner_id, message_id) |
| `audit_events` | id, actor_id nullable, event_type, resource_type, resource_id, run_id nullable, outcome, safe_metadata, created_at |
| `llm_usage` | id, run_id/job_id nullable, operation, model, price_version, input_tokens, cached_input_tokens, output_tokens, reserved_usd, actual_usd nullable, status, provider_request_id nullable, created_at |

LangGraph checkpoint tables được tạo bằng setup/migration của checkpointer trong schema riêng. Không tự coi application `agent_runs` là thay thế cho checkpoint storage.

### 13.3. Constraints và indexes bắt buộc

- Unique `agent_runs(actor_id, client_request_id)`.
- Partial unique index: một run active/conversation cho queued/running/waiting_approval/resume_queued.
- Unique `tickets.approval_id`; FK và not-null áp dụng cho mọi ticket tạo từ agent.
- Current version phải thuộc đúng document; dùng composite constraint hoặc validation trong transaction publish có test.
- Unique document/version_label và ingestion identity theo document/version/checksum/parser/chunker/embedding config.
- Index `messages(conversation_id, created_at, id)`, `run_events(run_id, sequence)`.
- Index `tickets(owner_id, status, created_at)` và `tickets(department_id, status, updated_at)`.
- Index visibility/department/current version; GIN search_vector. Exact vector search ban đầu chưa cần ANN index.
- Memory active có unique(owner_id, scope_key, fact_key); scope_key là user hoặc device:<uuid>, được server tạo. Episodic unique theo owner/ticket.
- Unique memory_jobs(source_run_id, memory_epoch, extractor_version).
- Index queued jobs/status/lease_until để reconcile.
- App DB role không có DDL; migrations chạy bằng migration role. Audit chỉ append qua application service.

Ownership kiểm tra ở service/repository trên mọi đường HTTP, job và MCP. UI ẩn nút không phải kiểm soát quyền. Chưa thêm RLS vào V1; test trực tiếp query/service để tránh giả định role SQL mặc định tự bảo vệ.

## 14. API contract

### 14.1. Quy ước chung

Prefix `/api/v1`; JSON snake_case; timestamps ISO-8601 UTC. API tự sinh request_id. Danh sách dùng cursor pagination, default limit=20, max=100.

Session dùng opaque random token trong HttpOnly cookie, lưu hash trong PostgreSQL; không dùng JWT cho V1 vì chỉ có web cùng backend và cần revoke nhanh. Cookie SameSite=Lax, Secure trên HTTPS; session hết hạn sau 8 giờ.

State-changing requests cần CSRF token gắn session và kiểm tra Origin. Dev frontend proxy `/api` về FastAPI; production phục vụ cùng origin. Token không được đưa vào URL.

Error envelope:

```json
{
  "error": {
    "code": "APPROVAL_EXPIRED",
    "message": "Bản xác nhận đã hết hạn. Hãy tạo yêu cầu mới.",
    "request_id": "uuid"
  }
}
```

Quy ước: 401 chưa đăng nhập, 403 thao tác bị cấm theo role, 404 object không tồn tại/không thuộc scope, 409 conflict, 410 approval expired, 413 quá lớn, 422 input sai, 429 quá quota, 503 dependency unavailable. Không lộ object trái quyền qua thông báo khác biệt.

### 14.2. Endpoint cần xây

| Method + path | Input chính | Output/hành vi |
|---|---|---|
| POST /auth/login | email, password | 200, set cookie, csrf token; lỗi credentials chung |
| GET /auth/me | session | User profile, role, department, csrf token |
| POST /auth/logout | CSRF | 204, revoke session |
| GET/POST /devices | label khi tạo | Chỉ thiết bị của user |
| GET/POST /conversations | title nullable, selected_device_id nullable | List/create conversation của user |
| GET /conversations/{id} | — | Metadata và active_run nếu có |
| GET /conversations/{id}/messages | cursor | Messages và sources còn được phép đọc |
| POST /conversations/{id}/runs | content, client_request_id, device_id nullable | 202: run_id, status, events_url |
| POST /conversations/{id}/ticket-drafts | title, description, issue_type, severity, device_id nullable, client_request_id | 202: manual_ticket run_id, dùng cùng graph approval |
| GET /runs/{id} | — | Trạng thái, outcome, result_message_id, approval_id/ticket_id nếu có |
| GET /runs/{id}/events | Last-Event-ID hoặc after_sequence | SSE events đã lưu |
| POST /runs/{id}/cancel | version | Chỉ queued/waiting_approval; reject draft nếu có |
| GET /approvals/{id} | — | Preview đúng owner, version, expires_at |
| POST /approvals/{id}/decision | decision approve/reject, version | 202 cho approve/resume; trạng thái hiện tại nếu lặp |
| GET /tickets | status/cursor | Ticket của user |
| GET /tickets/{id} | — | Ticket user sở hữu hoặc IT/admin có quyền qua service |
| GET /it/tickets | status/cursor | IT đúng phòng ban, admin toàn bộ |
| PATCH /it/tickets/{id} | status, resolution_note, version | Update + ticket event, kiểm tra transition |
| GET /admin/documents | cursor | Document/version/job status |
| POST /admin/documents | multipart file + metadata | 202: document_id, version_id, job_id |
| POST /admin/documents/{id}/versions | file + metadata | 202, tạo version draft |
| GET /admin/ingestion-jobs/{id} | — | stage/progress/error |
| POST /admin/ingestion-jobs/{id}/retry | — | Chỉ failed, cùng identity |
| GET /admin/document-versions/{id}/preview | — | Extracted text và metadata để duyệt |
| POST /admin/documents/{id}/publish | version_id, expected_document_version | Atomic publish hoặc 409 |
| PATCH /admin/documents/{id} | visibility, department_id, archived, version | Đổi ACL/archive và access_version |
| GET /documents/{id}/versions/{version_id}/download | — | Kiểm tra ACL trước đọc file; download attachment |
| GET /sources/{chunk_id} | — | Source metadata/excerpt, kiểm tra ACL và trạng thái |
| GET/PATCH /admin/services/{service_id} | status, fault_mode khi patch | Mô phỏng, chỉ demo mode |
| GET/PATCH /memory/settings | enabled khi patch | Settings + epoch hiện tại |
| GET /memories | status/cursor | Pending/active memory của user |
| PATCH /memories/{id} | decision accept/reject hoặc value, version | Xác nhận hoặc tạo revision có kiểm soát |
| DELETE /memories/{id} | — | Xóa nội dung, tăng memory_epoch |
| DELETE /memories | — | Xóa tất cả memory của user, tăng epoch |
| PUT /messages/{id}/feedback | rating up/down, reason nullable | Upsert feedback cho message được phép xem |
| GET /health/live | — | Tiến trình đang chạy |
| GET /health/ready | — | DB/Redis thiết yếu sẵn sàng, không gọi model |

Các endpoint GET/POST ghép trong bảng được implement thành route riêng. OpenAPI là nguồn sinh types frontend; response models cho các API quan trọng phải được viết ở M1/M3 trước UI phụ thuộc.

### 14.3. Chat và SSE

POST run commit message + queued run trước khi enqueue. Nếu enqueue lỗi sau commit, vẫn trả 202 với run_id để client theo dõi; reconciler sẽ enqueue lại. Gửi lại cùng client_request_id phải trả run cũ.

SSE chỉ đọc events thuộc run của user, không chạy agent. Các event type:

```text
run.queued
run.started
workflow.status
approval.required
approval.decided
message.completed
run.completed
run.failed
run.cancelled
```

Event có `sequence, run_id, type, timestamp, payload`; lưu PostgreSQL trước khi phát. Browser reconnect gửi Last-Event-ID, lấy các sequence chưa nhận; nếu history event đã hết retention thì tải run/messages snapshot.

API có thể poll event table mỗi 1 giây trong V1; heartbeat SSE mỗi 15 giây. Không dùng Redis Pub/Sub làm nguồn dữ liệu duy nhất. Không cần giữ DB connection riêng suốt thời gian browser chờ.

Cancel run đang running trả 409 vì write có thể đã commit; UI chỉ hiện nút hủy khi queued/waiting_approval. Backend vẫn có deadline để kết thúc job bị treo.

## 15. Queue, retry và recovery

### 15.1. Các queue

| Queue | Worker | Công việc |
|---|---|---|
| agent | Agent worker, concurrency=2 khởi đầu | Run/resume LangGraph |
| background | Background worker, concurrency=1 | Ingestion và memory extraction |
| maintenance | Background worker | Reconcile, expire approval, cleanup |

Celery beat chỉ phát lịch; reconcile code chạy trong background worker. Job dài có timeout để maintenance không bị chặn vô hạn. Queue message chỉ chứa ID; worker đọc dữ liệu/quyền mới nhất từ DB.

Database là nguồn trạng thái job. Redis delivery có thể lặp, nên mọi task phải claim và kiểm tra trạng thái trước khi làm việc. Không dựa vào Celery result backend làm API status.

Celery dùng JSON serialization, prefetch=1, acks_late cho task đã idempotent và cấu hình worker-lost redelivery có bounded attempts. Delivery/retry vẫn được kiểm soát bằng trạng thái DB; không giả định acks_late tự xử lý mọi kiểu worker crash. [Celery tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html).

### 15.2. Khoảng trống giữa DB và queue

- API commit queued/resume_queued/job record rồi enqueue Redis.
- Reconciler chạy mỗi 30 giây: tìm queued chưa được worker claim sau 30 giây, enqueue lại bằng stable job ID.
- Worker claim bằng atomic update/row lock. Delivery trùng khi job đã chạy/xong là no-op hoặc trả kết quả cũ.
- Job running có heartbeat/lease; stale chỉ được reclaim khi không còn executor giữ run lock.
- Số attempt tối đa 3 cho job, cộng dồn budget; action có receipt thì không execute lại.
- Expired approval làm run kết thúc với outcome approval_expired và event rõ ràng; không giữ partial unique active run vô hạn.

Không cam kết “exactly once” cho queue hay model call. Mục tiêu là task có thể chạy lại nhưng mỗi approval chỉ tạo một ticket trong DB.

### 15.3. Retry policy

Một nơi duy nhất quản lý retry cho provider calls; cấu hình SDK để tránh nhân retry giữa SDK, graph và Celery. Model timeout/429/5xx được retry tối đa một lần trong remaining budget, thêm exponential backoff có jitter.

Không retry permission failure, invalid arguments, approval rejected/expired, quota hết hoặc file không hỗ trợ. Số model calls tối đa bốn/run tính cả retry/repair; provider call thành công có thể được dùng lại qua checkpoint/tool-call records.

Read tool có thể retry. Ticket write timeout phải tra receipt theo approval_id trước. Chưa biết kết quả thì trả unknown và reconcile, không tuyên bố thất bại chắc chắn rồi tạo ticket mới.

### 15.4. Failure behavior

| Lỗi | Hành vi bắt buộc |
|---|---|
| OpenAI timeout | Retry có giới hạn; sau đó báo không thể trả lời, giữ lịch sử và cho tạo draft bằng form có dữ liệu đã nhập |
| OpenAI quota/budget hết | Không tạo model call mới; xem lịch sử/ticket vẫn dùng được |
| PostgreSQL không sẵn sàng | Readiness fail, business operations trả 503; không dùng dữ liệu memory làm thay DB |
| Redis không sẵn sàng | Chat/upload/approve mới trả 503 trước commit khi phát hiện; read DB vẫn hoạt động; race sau commit dùng queued record + reconcile |
| Langfuse không sẵn sàng | Local logs và application audit vẫn ghi; user request không thất bại vì trace |
| MCP server chết | Restart cho read khi còn budget; write lookup receipt trước retry |
| Worker chết khi chờ approval | Approval đã lưu, worker không cần chạy; refresh vẫn hiển thị draft |
| Worker chết sau ticket commit | Retry tìm ticket bằng approval_id và hoàn thiện receipt |
| Ingestion bị ngắt | Version đang publish vẫn hoạt động; retry version draft bằng checksum |
| Memory job bị ngắt | Chat thành công; retry không vượt epoch/consent |

Form tạo ticket khi model không sẵn sàng dùng cùng validate → approval → ticket service. UI nhập đủ title/description/issue_type/severity rồi gọi `POST /conversations/{id}/ticket-drafts` tại mục 14. Chỉ tạo run mới khi run trước đã kết thúc hoặc đã hủy draft; form này vẫn cần DB/Redis/MCP hoạt động.

## 16. OpenAI và kiểm soát chi phí

### 16.1. Cấu hình ban đầu

| Công việc | Model/API chọn để triển khai |
|---|---|
| Agent, draft và memory extraction | `gpt-4.1-mini-2025-04-14` qua Responses API |
| Embeddings | `text-embedding-3-small`, 1.536 dimensions |
| Thí nghiệm giảm giá sau baseline | `gpt-4o-mini-2024-07-18`, chỉ thay config nếu đạt evaluation gate |

GPT-4.1 mini có function calling, structured outputs và không có reasoning step, phù hợp baseline task có phạm vi hẹp. Việc chọn model này là quyết định khởi đầu của dự án, không phải khẳng định nó tốt nhất trên dataset chưa đo. Snapshot và quyền truy cập cần được smoke-test với account ở M0. [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

Embeddings default 1.536 dimensions; schema phải kiểm tra vector đúng dimension. Đổi embedding model/dimensions cần tạo index version mới và re-embed corpus, không trộn vector khác space. [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings).

### 16.2. Provider contract

```text
generate(messages/items, tool_schemas, reply_schema, limits)
  → tool_calls hoặc typed final_reply + usage + provider_request_id

embed(texts, model, dimensions)
  → vectors + usage
```

Responses API dùng custom function tools, strict schemas và server validation; không dùng hosted file search vì retrieval của dự án nằm trong PostgreSQL. Input của lượt sau giữ đúng tool call/result pairing và call_id. Schema chuyển sang JSON Schema hợp lệ, additionalProperties=false và nullable fields khai báo tường minh. [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling).

Final reply schema:

```text
answer_markdown: string
citations: list[source_id]
outcome: answered | needs_input | escalation_offered | resolved
follow_up_question: string | null
```

Outcome chỉ là đề xuất của model; backend kiểm tra nguồn xác nhận resolved. Ticket outcome/receipt do ứng dụng tạo. Không render success từ free-form text.

Tất cả OpenAI calls dùng `store=false` và chỉ gửi nội dung cần thiết. Cờ này không phải cam kết zero retention cho toàn bộ nhà cung cấp; lưu ý policy abuse monitoring riêng. Corpus V1 là dữ liệu giả/công khai. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

### 16.3. Budget khởi đầu

Người dùng yêu cầu tiết kiệm nhưng chưa đặt một số tiền cứng. Chọn default cấu hình có thể đổi: `APP_AI_DAILY_BUDGET_USD=1`, `APP_AI_MONTHLY_BUDGET_USD=10`. Đây là giới hạn cho ứng dụng khi được triển khai, không phải kết quả chi phí đã đo.

Giá tham khảo đã tra ngày 2026-09-15, USD/1 triệu token, standard API:

| Model | Input | Cached input | Output |
|---|---:|---:|---:|
| GPT-4.1 mini | 0,40 | 0,10 | 1,60 |
| GPT-4o mini | 0,15 | 0,075 | 0,60 |
| text-embedding-3-small | 0,02 | — | — |

Nguồn: [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small). Cập nhật price_version khi giá/model thay đổi.

Ví dụ 8.000 input + 1.000 output token cộng dồn cả run trên GPT-4.1 mini: khoảng 0,0048 USD/run, hay 4,80 USD/1.000 run. Đây là phép tính minh họa, chưa gồm retries, ingestion, memory, evaluation, thuế hoặc hosting.

- Trước mỗi call, reserve chi phí tối đa theo input/output cap bằng DB transaction; cộng cả reservations đang chạy khi kiểm tra quota.
- Sau response, đối soát usage thật; timeout không biết token phải giữ mức reservation bảo thủ, không ghi cost=0.
- Run, memory và ingestion đều qua cùng budget service. Không âm thầm tăng giá hoặc fallback sang model đắt hơn.
- Memory extraction tối đa một call/run, tối đa 2.000 input/500 output token, chỉ khi consent bật và có nội dung thuộc allowlist.
- Embedding cache key gồm model, dimensions, preprocessing_version và text hash; TTL 7 ngày, có namespace/quota.
- Query embedding cache có namespace actor_id; document embedding cache chỉ dùng nội bộ worker. Lọc secret trước embedding, không cache raw query text.
- Không cache retrieval results hoặc câu trả lời trong V1; tránh invalidation theo quyền và phiên bản.
- CI dùng fake provider mặc định; live eval chạy theo lệnh riêng với budget rõ.

## 17. Bảo mật và quản lý dữ liệu

### 17.1. Ranh giới tin cậy

User text, PDF/Markdown, memory candidate, tool result và model output đều là dữ liệu cần kiểm tra. Principal được backend nạp từ session/DB. Job/MCP không được lấy identity từ chat hoặc output của model.

Các kiểm soát cần có ngay từ mốc xây tính năng tương ứng:

- Argon2 cho password, opaque session được revoke, rate limit login, CSRF và exact Origin allowlist.
- Redis rate limit dùng atomic counter với TTL: login 5 lần/phút theo IP + định danh đã chuẩn hóa; chat/manual draft 10 lần/phút/user; upload 5 lần/giờ/admin. Response 429 có Retry-After.
- Admission limit: tối đa 2 run chưa kết thúc/user, 30 run queued toàn hệ thống; đầy queue trả 503 trước tạo record mới. Một conversation vẫn chỉ có một active run.
- Role/owner filters trên conversation, source download, ticket, memory, SSE và approval.
- Admin route và tool executor sử dụng cùng policy/service tests; agent không có tool quản trị.
- Parameterized SQL; filesystem path bằng UUID/storage key do server tạo.
- Render Markdown với raw HTML tắt; không tải remote images từ model; link source phải do server cấp.
- Không đưa password, access token, private key vào model/memory/trace; redact trước các sink, không chỉ trước logs.
- Prompt chỉ định retrieved text là evidence; tool allowlist và enforcement là lớp kiểm soát độc lập.
- Cấm các hướng dẫn xử lý lỗi bằng tắt xác minh TLS, tiết lộ secret hoặc gọi shell; với thao tác hệ thống chỉ đưa runbook được cho phép và điều kiện áp dụng.
- Kiểm tra quyền lại trước publish answer và trước ticket write; account inactive không được resume action.

Đánh giá prompt injection phải có trường hợp sử dụng tool vốn được phép để gửi dữ liệu nhạy cảm vào ticket, không chỉ thử gọi một tool delete không tồn tại. Approval preview phải là đúng dữ liệu server sẽ ghi.

### 17.2. Retention mặc định cho demo

| Dữ liệu | Quy tắc |
|---|---|
| Session | 8 giờ; revoke khi logout |
| Run events | 7 ngày; hết thời gian thì reconnect đọc snapshot |
| Conversation/messages/checkpoints | 90 ngày, cleanup có phối hợp |
| Memory pending | 7 ngày, hết hạn thì loại |
| Memory active/incident lookup | 90 ngày; người dùng xóa sớm được |
| Approval | Hiệu lực 15 phút; metadata/audit giữ 90 ngày |
| Ticket và ticket events | Giữ trong vòng đời demo; reset riêng |
| Ingestion lỗi và file mồ côi | Dọn sau 7 ngày |
| Tài liệu/current versions | Giữ đến khi archive; file version cũ theo manifest/reference |
| Langfuse raw I/O | Tắt mặc định; nếu bật với dữ liệu giả phải ghi rõ retention thực tế của project |
| Audit/usage metadata | 90 ngày; không lưu secrets hoặc raw prompt |

Cleanup không được phá FK: khi giữ ticket lâu hơn chat, giữ conversation stub không còn nội dung hoặc chuyển FK được phép sang null trong cùng cleanup policy. Pending/running approval được giải quyết trước khi xóa checkpoint. Tài liệu đang được citation tham chiếu giữ metadata để UI biết source đã retired.

Chính sách này dành cho demo với dữ liệu giả. Nếu đưa dữ liệu công ty thật vào, phải thiết kế lại SSO, quyền dữ liệu, retention của nhà cung cấp và quy trình vận hành trước khi pilot.

## 18. Observability và feedback

- Mỗi request có request_id; mỗi run có trace_id liên kết conversation và pseudonymous user ID.
- Trace các span: queue_wait, context_build, retrieval/embed/lexical/vector, model_call, MCP tool, approval_wait, final_validation, memory_job.
- Langfuse Cloud là trace sink của V1; bật từ M2. Self-host yêu cầu thêm các thành phần dữ liệu/worker và được chuyển sang V2. [Langfuse self-hosting](https://langfuse.com/self-hosting).
- Structured logs/audit trong ứng dụng là dữ liệu phục vụ kiểm tra business actions; Langfuse không thay thế audit.
- `LOG_PROMPTS=false` mặc định; chỉ gửi IDs, token usage, latency, outcome, model/prompt version. Không bật tự động capture I/O ở wrapper nếu chưa đi qua redaction.
- Lỗi export trace không chặn chat; log trạng thái telemetry degraded.
- Feedback up/down gắn message_id và trace_id; dislike reason gồm wrong_answer/wrong_source/outdated/tool_error/other.
- Feedback người dùng được review trước khi thêm vào golden dataset.

Dashboard/report tối thiểu:

| Nhóm | Chỉ số |
|---|---|
| System | Request/error rate, queue depth, queue wait, run latency p50/p95 |
| LLM | Calls/run, input/output/cached tokens, actual và reserved cost |
| Agent | Outcome, steps, tool failure, escalation rate, approval rejection |
| RAG | Retrieval latency, nguồn được chọn, corpus/embedding/chunker version |
| Memory | Candidate/accept/reject counts, stale/epoch rejects, correct-use rate |
| Reliability | Duplicate job suppressed, approval expired, recovered ticket receipts |

Đo riêng thời gian backend hoạt động và thời gian chờ người dùng approve. Tên span thể hiện công việc, không công khai chain-of-thought. SDK/capture configuration theo phiên bản đã pin. [Langfuse SDK overview](https://langfuse.com/docs/observability/sdk/overview).

## 19. Kiểm thử và evaluation

### 19.1. Các tầng kiểm thử

1. Unit: policy, tool schemas, severity rules, canonical hash, state transitions, context budget, memory allowlist.
2. Integration với PostgreSQL/pgvector và Redis thật: ACL retrieval, publish version, job replay, ownership, transactions.
3. Contract: tool registry ↔ MCP discovery, stdio call/result, provider schema, OpenAPI response models.
4. Web E2E: login → chat → citation → preview → approve → ticket; upload/publish; cross-conversation memory.
5. Live evaluation: dùng OpenAI thật trên bộ case đóng băng, chạy ngoài CI mặc định.

Fake provider giúp test orchestration ổn định; không dùng kết quả fake để công bố chất lượng model.

### 19.2. Dataset

M0 có 30 case để định hướng; V1 hoàn chỉnh có tối thiểu 120 case:

| Nhóm | Số case dự kiến |
|---|---:|
| RAG, gồm Việt/Anh và không có câu trả lời | 40 |
| Live status | 15 |
| Troubleshooting/escalation/ticket | 20 |
| Memory nhiều lượt/nhiều thiết bị | 15 |
| Quyền dữ liệu/prompt injection | 20 |
| Dependency failure/recovery | 10 |

Chia 80 development + 40 holdout, phân tầng theo nhóm. Các paraphrase của cùng incident/document task phải cùng split. Holdout không được dùng chỉnh prompt; khi đã dùng để quyết định thiết kế thì chuyển nó sang development và bổ sung holdout mới.

Schema case:

```text
case_id, split, scenario_group, language
actor_fixture, initial_db_state, document_snapshot
messages/interaction_script
expected_outcome, allowed_tool_sequences, forbidden_actions
relevant_evidence: document_key + version + section/span
required_answer_facts, forbidden_answer_facts
expected_db_changes, injected_failures, rubric_version
```

Ground truth retrieval dựa trên evidence span/document version, không cố định chunk IDs vì thay chunker sẽ đổi chunk. No-answer cases được đánh giá riêng, không cho relevant_docs rỗng vào mẫu số Recall@K.

### 19.3. Release gates

Các ngưỡng sau là mục tiêu ban đầu, không phải kết quả đã đạt. Nếu không đạt, ghi rõ nguyên nhân và giới hạn; không thay ngưỡng sau khi xem holdout chỉ để báo cáo đẹp.

| Gate | Điều kiện V1 |
|---|---|
| G-01: phân quyền | 0 lần lộ dữ liệu trong automated ACL tests, kể cả source title, history, memory, SSE |
| G-02: side effects | 0 ticket khi chưa approve/sai owner/expired/arguments thay đổi |
| G-03: duplicate/recovery | Mỗi approval đúng một ticket qua double-click, retry, concurrent job và crash sau commit |
| G-04: retrieval | Recall@5 ≥ 0,85 trên answerable retrieval cases có scope hợp lệ |
| G-05: citations | 100% source IDs hợp lệ; ≥ 90% câu trả lời có claim được nguồn hỗ trợ theo rubric review |
| G-06: answerability | ≥ 90% no-answer cases chọn hỏi thêm/abstain/escalate thay vì bịa chính sách |
| G-07: task success | ≥ 85% trên end-to-end case phù hợp, chấm cả tool arguments và DB effects |
| G-08: memory | ≥ 90% scripted memory tasks dùng đúng fact/device; 0 cross-user hoặc deleted-memory reuse |
| G-09: performance | P95 end-to-end ≤ 20 giây ở 3 lượt đồng thời, workload được ghi rõ, không tính approval wait |
| G-10: reproducibility | Máy sạch chạy setup, seed, tests và demo theo README; không cần dữ liệu private |

Gate bảo mật bằng 0 trên test suite không có nghĩa hệ thống đã được chứng minh an toàn với mọi input. Báo cáo phải có số case, số lần chạy và các tình huống chưa kiểm thử.

### 19.4. Regression cases bắt buộc

- Hai employee khác phòng ban đọc chéo ticket/conversation/source/memory, kể cả truy cập URL trực tiếp.
- User cùng phòng ban vẫn không đọc ticket cá nhân của nhau.
- Admin đổi document ACL sau retrieval nhưng trước final answer; history/source download không để lộ nội dung.
- Direct MCP call thiếu actor/run context bị từ chối.
- Approval khác owner, hết hạn, replay, sửa arguments hoặc inactive account bị từ chối.
- Hai approve cùng lúc và worker chết sau DB commit không tạo trùng.
- Manual ticket draft khi OpenAI bị tắt vẫn đi qua preview/approval và tạo đúng một ticket.
- Resume sau restart khôi phục draft và receipt đúng run.
- PDF chứa chỉ dẫn “bỏ kiểm tra” hoặc “gửi secret vào ticket” không thực hiện được tác động đó.
- User có Ubuntu trên laptop và Windows trên desktop; không ghi đè OS lẫn nhau.
- Tắt/xóa memory trong lúc extraction chạy; epoch cũ không được commit.
- Publish tài liệu lỗi/ingest dở không làm mất current version.
- Refresh SSE không tạo message/run/action mới.
- Queue delivery trùng; mất Redis giữa DB commit và enqueue; job được reconcile.
- OpenAI timeout nhưng chưa rõ usage; budget không bị hoàn lại như thể call miễn phí.

### 19.5. Benchmark/report

So sánh ba cấu hình trên cùng data/model/prompt budget: RAG baseline; agent + tools không memory; agent + tools + memory. Báo riêng nhóm task cần tool/memory; không dùng việc baseline không hỗ trợ write để kết luận retrieval của agent tốt hơn.

Live agent cases chạy tối thiểu ba lần, báo trung bình và biến động. LLM-as-judge chỉ hỗ trợ chấm; tool permissions và DB effects chấm bằng code, một phần câu trả lời được human review. Artifact lưu run IDs, model snapshot, git commit, corpus checksum, seed, concurrency, token totals, latency và cost.

## 20. Cấu trúc repository và triển khai local

### 20.1. Cấu trúc đích

```text
backend/
  pyproject.toml
  uv.lock
  migrations/
  app/
    main.py
    config.py
    api/                  # auth, conversations, runs, tickets, docs, memory
    auth/                 # sessions, policies, CSRF
    agent/                # graph, state, nodes, context, checkpoints
    rag/                  # parser, chunker, ingestion, retrieval, citations
    memory/               # extraction, lifecycle, retrieval
    tools/                # schemas, registry, executor
    mcp_server/           # entrypoint và business-tool adapters
    services/             # tickets, approvals, documents, budget
    repositories/         # queries có scope
    db/                   # models, session factory
    providers/            # OpenAI + fake provider
    jobs/                 # Celery tasks, reconcile, cleanup
    observability/        # safe logs, Langfuse, usage
    prompts/              # versioned prompts/schema
  tests/
    unit/
    integration/
    contract/
frontend/
  src/
    api/
    features/
      auth/
      chat/
      tickets/
      documents/
      memory/
      services/           # trang admin điều khiển dịch vụ mô phỏng
    components/
  package.json
  package-lock.json
  e2e/
data/
  seed/
  knowledge/
  manifests/
evals/
  cases/
  rubrics/
  runner/
reports/
docs/
  implementation-roadmap.md
  architecture.md
  demo-script.md
  adr/
  archive/plan-original.md
infra/
  compose.yaml
  Dockerfile.backend
  Dockerfile.frontend
.env.example
.github/workflows/ci.yml
Makefile
README.md
plan.md
```

Cây trên là cấu trúc đích. Các thư mục kiến trúc đã được tạo cùng `PLAN.md`; WP-01 đã bổ sung backend/frontend runtime, hai lockfile, Makefile và CI workflow. Migration, Compose, seed/evaluation data và code nghiệp vụ vẫn là đầu ra của các WP sau. Xem [mục lục đầy đủ](docs/implementation-roadmap.md).

### 20.2. Compose

Services bắt buộc: `frontend, api, worker-agent, worker-background, scheduler, postgres, redis`. MCP subprocess nằm trong worker-agent, Langfuse Cloud và OpenAI là dịch vụ bên ngoài.

- Volumes: postgres data, redis data/AOF, document storage.
- Redis cấu hình noeviction để không làm mất queue keys; cache có TTL/kích thước giới hạn, không chiếm hết RAM.
- Host chỉ mở frontend, và API/docs ở localhost khi develop; DB/Redis không mở public.
- Reverse proxy frontend chuyển `/api` tới API, tắt buffering cho SSE.
- Migration là one-off step trước chạy app; seed là lệnh rõ ràng, không tự chạy mỗi restart.
- Worker-agent concurrency=2; worker-background concurrency=1. Beat chỉ một instance.
- Mỗi Celery task tạo/đóng async DB/OpenAI/MCP clients trong đúng event loop; không reuse client async được tạo trước fork hoặc loop khác.
- Healthchecks riêng DB/Redis/API; OpenAI/Langfuse không được gọi liên tục từ healthcheck.
- Public hosting nếu làm sau V1 phải thêm TLS, secret management, resource limits và access gating cho demo.

### 20.3. Configuration

```text
APP_ENV=development
DEMO_MODE=true
DATABASE_URL=<secret>
MIGRATION_DATABASE_URL=<secret>
REDIS_URL=<secret>
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-4.1-mini-2025-04-14
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
LANGFUSE_PUBLIC_KEY=<project key>
LANGFUSE_SECRET_KEY=<secret>
LANGFUSE_BASE_URL=<project region endpoint>
LOG_PROMPTS=false
APP_AI_DAILY_BUDGET_USD=1
APP_AI_MONTHLY_BUDGET_USD=10
DOCUMENT_STORAGE_PATH=/data/documents
DEMO_SEED_PASSWORD=<local demo secret>
```

Các giá trị secret chỉ xuất hiện ở environment runtime, không commit. V1 cần API OpenAI đang có billing/access và Langfuse project; unit/integration/E2E fake-mode không cần các key đó.

### 20.4. Developer commands cần cung cấp

```text
make bootstrap       # kiểm tra prerequisite và cài dependencies đã lock
make up              # start Compose
make migrate         # Alembic + setup checkpoint storage
make seed            # dữ liệu tự tạo, idempotent
make test            # unit/integration/contract fake mode
make test-e2e        # web scenarios
make eval            # live evaluation có quota guard
make demo            # hướng dẫn/khởi chạy demo đã seed
make backup          # database dump + document manifest/files
make restore-test    # restore vào database/volume test riêng
```

Không dùng reset database thật trong tests. README ghi cấu hình máy thử nghiệm; mục tiêu local với khoảng 4 CPU/8 GB RAM dành cho stack là giả định để đo lại, không phải minimum đã benchmark. Không cần GPU.

## 21. Roadmap thực thi

Ước lượng dưới đây là giờ làm việc tập trung, giả định đã có nền tảng Python/backend nhưng phải tự làm UI và tích hợp các thư viện. Vì chưa chốt số giờ/tuần, không ấn định ngày bàn giao.

| Mốc | Nội dung | Giờ dự kiến | Kết quả/điều kiện kết thúc |
|---|---|---:|---|
| M0 | Skeleton, ADR, model/MCP/checkpointer spikes, seed spec, 30 evaluation cases | 4–6 | Cấu hình dependency tương thích, API/schema contract khởi đầu, không còn rủi ro tích hợp cơ bản chưa thử |
| M1 | Compose, DB migrations, session auth, RBAC, web shell, Celery/Redis | 12–18 | Login, ownership negative tests, job tạo/đọc status, CI fake-mode chạy |
| M2 | Seed corpus, ingestion cơ bản, RAG graph, chat/SSE/citations, Langfuse trace | 18–28 | Demo hỏi tài liệu có nguồn chạy end-to-end; baseline được ghi |
| M3 | MCP status/ticket reads, ticket draft, approval, atomic write, UI ticket | 28–40 | UC-02/04/05/09 chạy; duplicate/permission/crash-after-commit tests pass |
| M4 | Recovery/reconcile, full document admin/versioning, ACL và output enforcement | 18–26 | Refresh/restart/dependency errors có hành vi đúng; publish/ACL tests pass |
| M5 | Device-scoped memory, consent, confirm/edit/delete, cross-conversation context | 24–36 | UC-06/11/12 chạy; multi-device và epoch race tests pass |
| M6 | 120-case dataset, live eval, feedback, load/cost report | 16–24 | Báo cáo gates, baseline comparison, lỗi chất lượng quan trọng được sửa |
| M7 | Hoàn thiện UI/README/demo, backup-restore drill, clean-machine verification | 24–36 | V1 đủ năm thành phần yêu cầu và đạt Definition of Done |

Tổng xây dựng 144–214 giờ; cộng khoảng 25% cho lỗi tích hợp và chỉnh chất lượng: khoảng 180–270 giờ. Nếu làm 40 giờ/tuần, khoảng 5–7 tuần; 20 giờ/tuần, khoảng 9–14 tuần. Đây là ước lượng lập kế hoạch, sẽ cập nhật sau M2 bằng thời gian thực tế.

Mốc demo sớm là M2, khoảng 34–52 giờ trước dự phòng. Các việc security, telemetry và test được làm cùng feature, không để dồn đến cuối.

### 21.1. Thứ tự các work package có thể bắt đầu code

| ID | Đầu việc | Phụ thuộc | Kiểm chứng bắt buộc |
|---|---|---|---|
| WP-01 | Khởi tạo backend/frontend, lock deps, env validation, lint CI | — | Fresh install/build; config thiếu secret báo lỗi rõ |
| WP-02 | Schema identity/conversation/run, session login/CSRF | WP-01 | Wrong owner/login/CSRF bị chặn |
| WP-03 | Celery queues, run status/event store, SSE replay | WP-02 | Enqueue/read/reconnect không tạo run mới |
| WP-04 | Seed tài liệu/fixtures, parse/chunk/embed draft | WP-01, WP-02 | Metadata/page preservation, duplicate ingest |
| WP-05 | Scoped hybrid retriever + citation endpoints | WP-04 | Company/department/IT-only cases; no-answer baseline |
| WP-06 | OpenAI provider + LangGraph RAG flow + context budget | WP-03, WP-05 | UC-01/03, bounded loop, Langfuse trace |
| WP-07 | Business services + MCP contract và read tools | WP-02 | Actor context, allowed service IDs, own tickets |
| WP-08 | Approval persistence + resume + ticket transaction | WP-03, WP-06, WP-07 | Double approve, replay, timeout, args mismatch |
| WP-09 | Chat approval card và ticket/IT UI | WP-08 | Browser E2E tạo/resolve/reopen ticket |
| WP-10 | Reconciler, receipt recovery và fault presets | WP-08 | Redis enqueue race, worker crash, lease/lock recovery |
| WP-11 | Admin documents/versioning/ACL UI | WP-05 | Upload → preview → publish; old version và revoked ACL |
| WP-12 | Memory lifecycle/context + settings UI | WP-06, WP-09 | Consent, device isolation, delete-while-job-running |
| WP-13 | Full eval/feedback/performance/cost artifacts | WP-09, WP-10, WP-11, WP-12 | G-01 đến G-09 có kết quả và mẫu số |
| WP-14 | README, demo video, restore drill và release checklist | WP-13 | G-10, reviewer chạy độc lập |

WP-01 đến WP-06 ưu tiên trước để có demo. Người xây dựng có thể quay lại cải thiện một work package khi evaluation chỉ ra lỗi; không mở thêm domain/tool trước khi luồng hiện tại đạt gate.

### 21.2. Khi cần rút ngắn lịch

Giữ nguyên MCP, LangGraph, memory, Redis, Langfuse và các đường an toàn. Giảm độ bóng UI, số tài liệu ban đầu, số trang admin phụ và số thí nghiệm model/reranker. Duy trì các test phân quyền, approval, idempotency và các case demo cốt lõi.

Nếu chưa đủ thời gian hoàn tất V1, công bố bản demo với danh sách tính năng đã làm và chưa làm; không đổi tên một mốc trung gian thành V1 hoàn chỉnh.

## 22. Definition of Done và bàn giao

- [ ] Clone repository, cấu hình environment, chạy Compose/migrate/seed theo README.
- [ ] Có đủ web chat, ticket, document admin và memory settings.
- [ ] UC-01 đến UC-12 chạy được; ba business tools thực sự đi qua MCP.
- [ ] LangGraph lưu checkpoint và resume approval sau restart.
- [ ] Memory dùng được ở conversation mới, đúng user/device và thao tác xóa/tắt có hiệu lực.
- [ ] Redis thực sự phục vụ queue/rate limit/cache; có test degradation/reconciliation.
- [ ] Langfuse có trace của luồng demo; metadata token/cost/outcome đúng và không lộ secret.
- [ ] Automated permission/approval/idempotency/recovery tests pass.
- [ ] Báo cáo evaluation có dataset split, số mẫu, model snapshot, source versions, cost và latency.
- [ ] Có kết quả các release gates; trường hợp không đạt được ghi rõ và chưa gọi là release hoàn chỉnh.
- [ ] Backup đã được restore thử sang database test riêng.
- [ ] Video demo khoảng 3–5 phút và script để reviewer tái hiện.
- [ ] Architecture/ADR giải thích single-company, stdio MCP, scoped memory, hybrid retrieval và trade-offs.

Tên portfolio đề xuất: **Stateful IT Support Agent with Evaluated RAG and Approval Workflows**.

CV mô tả các phần thực sự đã triển khai cùng số liệu đo được. Bản V1 được định vị là portfolio prototype có kiểm thử và đánh giá; mức enterprise production cần thêm vận hành và tích hợp thật.

## 23. Mở rộng sau V1

Chỉ chọn mục tiếp theo từ nhu cầu hoặc số liệu:

1. Reranker/HNSW khi retrieval hoặc latency cho thấy cần.
2. Thử model rẻ hơn với cùng release gates.
3. MCP Streamable HTTP và authentication nếu có client/process bên ngoài.
4. Một integration Jira/ServiceNow thật với reconciliation theo external ID.
5. SSO và policy dữ liệu trước một pilot nội bộ.
6. Langfuse self-host khi có lý do data/hosting; tính đủ dependencies và tài nguyên.
7. Long-term episodic vector retrieval khi số sự cố vượt khả năng structured lookup.
8. Self-host inference/quantization/load balancing như nhánh thí nghiệm riêng, có ngân sách GPU cụ thể.

## 24. Ghi chú tham chiếu

Các lựa chọn sản phẩm, schema, API, budget, timeline và release gates trong tài liệu là thiết kế của dự án dựa trên yêu cầu đã xác nhận. Tài liệu chính thức được dẫn ngay cạnh các chi tiết phụ thuộc thư viện/model.

Khi bắt đầu M0, kiểm tra version compatibility, model access và giá thực tế; ghi patch versions/snapshot vào lockfile và ADR. Mỗi thay đổi phạm vi cần sửa bảng mốc, API/schema liên quan và acceptance tests cùng lúc.
