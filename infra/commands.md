# Reproducible project commands

Các lệnh chính ở root `Makefile` dùng dependency đã khóa và cùng cấu hình Compose. AI mặc định là `fake`; không lệnh nào bên dưới tự gọi API trả phí.

## Luồng chạy demo

```bash
make bootstrap
make migrate
make seed
make up
```

- `bootstrap` chỉ tạo `.env` khi chưa tồn tại và build application images; không ghi đè cấu hình hiện có.
- `migrate` chạy Alembic bằng one-shot container có migration credential; chỉ upgrade schema.
- `seed` tạo hoặc cập nhật demo identity theo cách idempotent; không xóa dữ liệu.
- `up` dựng bảy service và chờ toàn bộ healthcheck. Frontend ở `127.0.0.1:5173`, API ở `127.0.0.1:8000` theo mặc định.
- `demo` gộp `migrate`, `seed`, `up` theo đúng thứ tự.
- `down` dừng stack nhưng giữ ba named volume PostgreSQL, Redis và document storage.

`POSTGRES_PASSWORD` và `DEMO_SEED_PASSWORD` phải được đặt trong `.env`. Không commit `.env`.

## Verification

```bash
make test
make test-e2e
make eval
make clean-verify
```

- `test` dựng PostgreSQL/Redis trong Compose project `it-support-agent-tests`, chạy toàn bộ backend test rồi lint, typecheck, unit test và build frontend. Project test cùng volumes được xóa khi kết thúc.
- `test-e2e` chạy Chromium trong Playwright image đã khóa. Các browser scenario hiện dùng API route fixtures để giữ kết quả deterministic.
- `eval` validate đủ 120 case và chạy development split với fake provider trong container; không cần OpenAI key.
- `clean-verify` tạo project có tên duy nhất, DB/Redis/document volumes mới, build images, chạy migration và seed, khởi động đủ bảy service rồi gọi readiness qua frontend proxy. Trap chỉ xóa đúng project tạm đó.

## Ranh giới dữ liệu

- Không command chuẩn nào chạy `down --volumes` trên project phát triển.
- Chỉ `test`, `eval` và `clean-verify` xóa volumes do chính project tạm của chúng tạo.
- Migration không downgrade hoặc reset database.
- Backup/restore có target riêng; restore drill không được phép trỏ vào database đang sử dụng.
- Live OpenAI chỉ chạy qua target riêng có opt-in rõ ràng; `test`, `eval` và CI luôn dùng fake provider.
