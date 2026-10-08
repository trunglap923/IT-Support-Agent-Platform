# Kịch bản demo và bằng chứng

Kịch bản này phân biệt hai chế độ:

- **Automated portfolio demo**: đã chạy bằng fake provider/fixtures, deterministic, không cần paid key.
- **Manual V1 demo**: role accounts, devices, service states, tickets và published corpus đã có; các bước vẫn chưa được tuyên bố đã chạy end-to-end thủ công nếu chưa ghi evidence.

## Chuẩn bị automated demo

```bash
cp .env.example .env
# đặt POSTGRES_PASSWORD và DEMO_SEED_PASSWORD
make clean-verify
make test
make test-e2e
make eval
```

Kết quả local gần nhất ngày 2026-10-08: clean stack 7/7 healthy; Alembic qua đủ 26
migration; backend 283 pass/1 skip; frontend lint/typecheck/build và 51 test pass; Playwright
21/21 pass; evaluation 120 case hợp lệ, 80/80 development checks và 160 reproducibility runs
cùng digest.

## Demo giao diện tối thiểu

```bash
make migrate
make seed
make up
```

1. Mở `http://127.0.0.1:5173`.
2. Login `employee.engineering@example.com` bằng `DEMO_SEED_PASSWORD`.
3. Mở `/chat`, tạo conversation và quan sát message/run status/SSE UI.
4. Mở `/tickets` và `/settings/memory` để trình bày candidate confirmation và fact controls.
5. Với fake provider, hỏi về VPN/Docker/GitLab để kiểm tra citation từ corpus đã publish.

## Automated feature evidence

| Hành vi | Cách trình bày | Bằng chứng |
|---|---|---|
| RAG có nguồn/no-answer | Chạy PostgreSQL system tests và retrieval baseline | `reports/rag-chat-baseline.md`, `reports/retrieval-baseline.md` |
| MCP actor isolation | Chạy contract/integration suite | `backend/tests/contract`, `backend/tests/integration/test_mcp_business_reads.py` |
| Approve/reject/double approve | Playwright + DB integration | `frontend/e2e/ticket-workflows.pw.ts`, ticket/approval tests |
| Resolve/reopen và role denial | Playwright deterministic workflow | `make test-e2e` |
| Document publish/revoke/ACL | Document browser workflow + PostgreSQL tests | `frontend/e2e/document-administration.pw.ts` |
| Memory confirm/edit/delete | Memory browser workflow + epoch tests | `frontend/e2e/memory-lifecycle.pw.ts` |
| Redis/worker failure recovery | Required integration tests | workflow recovery/failure recovery tests |
| Reproducible stack | Fresh Compose project/volumes | `make clean-verify` |
| Backup/restore | Isolated DB + volume drill | `make backup && make restore-test` |

## Manual V1 scenario

1. Employee hỏi cách xử lý Docker certificate; agent tìm runbook hiện hành và trả citation.
2. Khi thiếu evidence, agent hỏi thêm hoặc no-answer thay vì bịa.
3. Employee yêu cầu ticket; UI hiện draft/expiry, chưa có ticket trước approval.
4. Refresh, approve hai lần; DB chỉ có một ticket/receipt.
5. IT đúng scope resolve rồi reopen; employee khác không đọc được ticket.
6. Admin publish version tài liệu mới/revoke cũ; answer/history/source không lộ version bị thu hồi.
7. User bật memory, xác nhận device fact; conversation mới dùng đúng device. Sau delete/disable, lượt mới không dùng lại.
8. Admin đổi service status mô phỏng; agent đọc status qua MCP với trusted actor context.
9. Mở Langfuse trace đã lọc nếu có cấu hình live; không hiển thị secret/session/raw sensitive prompt.

## Live-model demo tùy chọn

Chỉ chạy khi chấp nhận chi phí và đã đặt `OPENAI_API_KEY`:

```bash
RUN_OPENAI_LIVE_SPIKE=1 make spike-openai-live
TEXT_PROVIDER=openai RUN_LIVE_EVAL=1 make eval-agent-live
```

Ghi rõ model snapshot, số lần chạy, token/cost và không dùng một lần demo thành tuyên bố chất lượng. Báo cáo hiện tại vẫn `not_ready` vì G-05–G-09 chưa được đo đủ.

## Nội dung chưa được tuyên bố hoàn tất

- video 3–5 phút chưa được ghi;
- account/department/device/service/ticket/published-document seed đã có;
- manual UC-01–UC-12 chưa có evidence trên một seeded environment;
- GitHub-hosted CI chưa có remote run evidence;
- production deployment/operations không nằm trong giai đoạn này.
