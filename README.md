# IT Support Agent Platform

Portfolio trợ lý IT: trả lời có nguồn, kiểm tra dịch vụ mô phỏng, tạo ticket có xác nhận và nhớ thông tin đã được người dùng đồng ý lưu.

## Trạng thái hiện tại

Đã khởi tạo cây thư mục và **57 kế hoạch module**. Mỗi `PLAN.md` có phạm vi, hợp đồng, tệp cần viết, phần phụ thuộc, checklist có mã và điều kiện hoàn thành.

Đây là bộ khung chuẩn bị code, **chưa phải ứng dụng chạy được**. Chưa có runtime, dependency lockfiles, migrations, Docker Compose hay test suite thực thi. Các tệp được liệt kê ở mục “Tệp dự kiến khi viết code” là đầu việc cần tạo, không phải tệp đã tồn tại.

## Bắt đầu từ đâu?

1. Đọc [kế hoạch tổng](plan.md) để nắm phạm vi V1 và quy tắc nghiệp vụ.
2. Mở [roadmap và mục lục kế hoạch module](docs/implementation-roadmap.md); bắt đầu WP-01.
3. Đọc `PLAN.md` của module sắp làm, tạo code cùng kiểm thử và chỉ đánh dấu hoàn thành khi đạt điều kiện trong file.
4. Nếu thay đổi thiết kế, cập nhật [ADR](docs/adr/PLAN.md), kế hoạch tổng và các module bị ảnh hưởng.

Ưu tiên WP-01 → WP-06 để có demo chat/RAG sớm; sau đó triển khai MCP, approval/ticket, recovery, document admin và memory theo phụ thuộc. Không cần viết đồng thời mọi thư mục.

## Cấu trúc chính

```text
backend/
  app/
    api/ auth/
    agent/context/
    rag/{ingestion,chunking,retrieval,citations}/
    memory/ tools/ mcp_server/
    services/{conversations,approvals,tickets,documents,budget,service_status}/
    repositories/ db/ providers/ jobs/ observability/ prompts/
  migrations/
  tests/{unit,integration,contract}/
frontend/
  src/
    api/ components/
    features/{auth,chat,tickets,documents,memory,services}/
  e2e/
data/{seed,knowledge,manifests}/
evals/{cases,rubrics,runner}/
reports/
docs/adr/
docs/archive/plan-original.md
infra/
.github/workflows/
```

Ký hiệu `{...}` trong cây rút gọn đại diện cho các thư mục con riêng. Mọi module nêu trên có `PLAN.md`; tài liệu archive được giữ nguyên.

| Khu vực | Kế hoạch đầu vào |
|---|---|
| Backend/API/agent | [backend/PLAN.md](backend/PLAN.md) |
| Frontend | [frontend/PLAN.md](frontend/PLAN.md) |
| Dữ liệu demo | [data/PLAN.md](data/PLAN.md) |
| Evaluation | [evals/PLAN.md](evals/PLAN.md) |
| Báo cáo | [reports/PLAN.md](reports/PLAN.md) |
| Vận hành local | [infra/PLAN.md](infra/PLAN.md) |
| CI | [.github/workflows/PLAN.md](.github/workflows/PLAN.md) |

## Quy ước và cấu hình

- Định hướng stack: Python/FastAPI, React/TypeScript, PostgreSQL/pgvector, LangGraph, MCP, Celery/Redis và Langfuse. Phiên bản tương thích và lockfiles được kiểm chứng ở WP-01/M0.
- [.env.example](.env.example) là mẫu cấu hình không có secret. Runtime validation và chế độ fake/live sẽ được triển khai ở WP-01; không gửi API key vào chat hoặc commit vào repo.
- [.python-version](.python-version), [.editorconfig](.editorconfig) và [.gitignore](.gitignore) thống nhất phiên bản Python dự kiến, định dạng và dữ liệu không commit.
- Các lệnh `make up`, `make test`, `make eval` trong kế hoạch tổng là đầu ra tương lai; hiện chưa có Makefile để chạy chúng.
- Dữ liệu mẫu phải là dữ liệu tự tạo/công khai có quyền sử dụng. Không kết nối VPN/GitLab/ticketing của doanh nghiệp thật trong V1.

Xem [bản đồ kiến trúc](docs/architecture.md) và [kịch bản demo dự kiến](docs/demo-script.md). Chỉ báo cáo metric và tính năng đã chạy kiểm chứng.
