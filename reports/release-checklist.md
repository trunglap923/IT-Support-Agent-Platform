# Release checklist — WP-14

Ngày kiểm chứng local gần nhất: 2026-10-08. Quyết định tổng thể: **NOT READY**.

Lý do: G-10 có local reproducibility evidence, nhưng G-05–G-09 chưa được đo đủ bằng live model/human review/full-stack workload. GitHub-hosted CI và manual V1 demo vẫn chưa có evidence.

## G-10 reproducibility

| Kiểm tra | Kết quả | Bằng chứng/giới hạn |
|---|---|---|
| Build production backend/frontend images | pass | Pinned bases, non-root, healthcheck; `make clean-verify` |
| Fresh PostgreSQL/Redis/document volumes | pass | Unique Compose project, không dùng volumes development |
| Migrate clean DB qua 26 revisions | pass | Alembic head `0026_memory_embedding_identity` |
| Seed demo data | pass | Business fixtures + 9 published docs/11 versions/41 fake-embedded chunks; rerun không nhân bản |
| Start complete stack | pass | 7/7 service healthy, readiness qua Nginx proxy |
| Backend suite | pass | 283 passed, 1 skipped trên isolated PostgreSQL/Redis |
| Frontend quality/build | pass | lint/typecheck, 51 tests, production build |
| Browser workflow suite | pass | 21 Playwright checks; desktop/mobile screenshots reviewed |
| Deterministic evaluation | pass | 120 valid cases; 80/80 development checks; 160 reproducibility runs cùng digest |
| Backup/restore drill | pass | Manifest verified; isolated DB/volume restored and cleaned |
| Markdown internal links | pass | 514 relative links checked after the Langfuse documentation update |
| Independent clean-machine reviewer | not run | Local isolated verification, chưa phải máy của reviewer khác |

G-10 status: **local_pass / independent_review_pending**. Đây không thay đổi overall release decision khi các gate khác còn `not_measured`.

## Release gates

| Gate | Status | Diễn giải |
|---|---|---|
| G-01 authorization | pass | 8/8 named regression tests; không suy rộng thành chứng minh an toàn tuyệt đối |
| G-02 side effects | pass | 3/3 approval/write regressions |
| G-03 duplicate/recovery | pass | 3/3 duplicate/crash/receipt regressions |
| G-04 retrieval | pass | Recall@5 9/9 trên development corpus/fake embeddings |
| G-05 citations | not measured | Source ID integrity có test; chưa human-review semantic claims |
| G-06 answerability | not measured | Fake contract 5/5 không đại diện live model |
| G-07 task success | not measured | Non-RAG eval cases còn scripted contracts |
| G-08 memory | not measured | Safety tests pass; chưa có agent accuracy denominator |
| G-09 performance | not measured | In-process fake P95 không phải full-stack workload |
| G-10 reproducibility | local pass | Independent reviewer/remote CI pending |

Chi tiết G-01–G-09 nằm tại [evaluation summary](evaluation-summary.md) và [product-quality.json](product-quality.json).

## Bàn giao đã có

- [x] README quick start, commands và giới hạn rõ ràng.
- [x] Architecture, ADR và trust boundaries.
- [x] Demo script tách automated evidence khỏi manual/live claims.
- [x] Troubleshooting cho port, auth/CSRF, readiness, stale container và restore.
- [x] Production images và complete local Compose stack.
- [x] Backup + integrity manifest + isolated restore drill.
- [x] CI definition cho static/unit/contracts/migration/integration/E2E/images/secret scan.
- [x] 120-case dataset, deterministic runner và reviewed local reports.

## Điều kiện còn thiếu trước khi gọi V1 release-ready

- [ ] Human review các claim/citation để đo G-05.
- [ ] Live-model no-answer/task/memory runs đủ repetitions để đo G-06–G-08.
- [ ] Full-stack concurrency-3 workload để đo G-09.
- [ ] Manual UC-01–UC-12 evidence trên seeded environment.
- [ ] GitHub Actions remote run pass trên commit bàn giao.
- [ ] Reviewer khác chạy README từ clean machine.
- [ ] Video demo 3–5 phút.

Deployment production không phải blocker của portfolio local V1 nhưng cần runbook riêng nếu mở scope: TLS, secrets manager, remote backup retention, monitoring/alerting và incident response.
