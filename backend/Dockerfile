# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime

ARG APP_UID=10001
ARG APP_GID=10001
ARG INSTALL_CROSS_ENCODER=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=120 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN --mount=type=secret,id=host_ca_bundle,required=false \
    --mount=type=cache,target=/root/.cache/uv \
    groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --create-home --home-dir /home/app app \
    && if [ -f /run/secrets/host_ca_bundle ]; then \
        PIP_CERT=/run/secrets/host_ca_bundle \
            python -m pip install --no-cache-dir uv==0.11.32; \
    else \
        python -m pip install --no-cache-dir uv==0.11.32; \
    fi

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN --mount=type=secret,id=host_ca_bundle,required=false \
    --mount=type=cache,target=/root/.cache/uv \
    if [ -f /run/secrets/host_ca_bundle ]; then \
        export SSL_CERT_FILE=/run/secrets/host_ca_bundle; \
    fi \
    && if [ "${INSTALL_CROSS_ENCODER}" = "true" ]; then \
        uv sync --system-certs --frozen --no-dev --no-install-project --extra cross-encoder; \
    else \
        uv sync --system-certs --frozen --no-dev --no-install-project; \
    fi

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
RUN mkdir -p /app/.storage/documents \
    && chown -R app:app /app/.storage /home/app
COPY --chown=app:app data/knowledge /app/seed-data/knowledge
COPY --chown=app:app data/manifests/documents.json /app/seed-data/manifests/documents.json

USER app:app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2).read()"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]

FROM runtime AS test

USER root
ARG INSTALL_CROSS_ENCODER=false
RUN --mount=type=secret,id=host_ca_bundle,required=false \
    --mount=type=cache,target=/root/.cache/uv \
    if [ -f /run/secrets/host_ca_bundle ]; then \
        export SSL_CERT_FILE=/run/secrets/host_ca_bundle; \
    fi \
    && if [ "${INSTALL_CROSS_ENCODER}" = "true" ]; then \
        uv sync --system-certs --frozen --all-groups --no-editable --extra cross-encoder; \
    else \
        uv sync --system-certs --frozen --all-groups --no-editable; \
    fi
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
