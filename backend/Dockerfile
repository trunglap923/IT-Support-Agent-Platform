# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --create-home --home-dir /home/app app \
    && python -m pip install --no-cache-dir uv==0.11.32

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
RUN uv sync --frozen --no-dev --no-editable \
    && mkdir -p /app/.storage/documents \
    && chown -R app:app /app/.storage /home/app

USER app:app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2).read()"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

FROM runtime AS test

USER root
RUN uv sync --frozen --all-groups --no-editable
COPY backend/tests /app/tests
COPY evals /workspace/evals
COPY data /workspace/data
COPY reports /workspace/reports
RUN mkdir -p /app/.pytest_cache \
    && chown -R app:app /app/tests /app/.pytest_cache /workspace

ENV PYTHONPATH=/workspace:/app
WORKDIR /workspace
USER app:app
CMD ["pytest", "/app/tests"]

FROM runtime AS production
