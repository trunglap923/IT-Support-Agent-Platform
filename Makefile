UV ?= uv
NPM ?= npm
PYTHON_VERSION ?= 3.12
UV_CACHE_DIR ?= /tmp/it-support-agent-uv-cache
NODE_IMAGE ?= node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5
PROJECT_UID := $(shell id -u)
PROJECT_GID := $(shell id -g)
FRONTEND_DOCKER = docker run --rm --user $(PROJECT_UID):$(PROJECT_GID) -e npm_config_cache=/tmp/npm-cache -v $(CURDIR)/frontend:/app -w /app $(NODE_IMAGE)

.PHONY: help bootstrap check backend-sync backend-format backend-check \
	frontend-install frontend-check frontend-install-docker frontend-check-docker \
	dev-backend dev-frontend dev-frontend-docker

help:
	@echo "WP-01 commands:"
	@echo "  make bootstrap              Install locked backend/frontend dependencies"
	@echo "  make check                  Run all checks using host npm"
	@echo "  make backend-check          Format check, lint, typecheck and tests"
	@echo "  make frontend-check         Lint, typecheck, tests and build"
	@echo "  make frontend-check-docker  Same frontend checks with Node 22 in Docker"
	@echo "  make dev-backend            Run FastAPI at http://127.0.0.1:8000"
	@echo "  make dev-frontend           Run Vite at http://127.0.0.1:5173"

bootstrap: backend-sync frontend-install

check: backend-check frontend-check

backend-sync:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs sync --directory backend --python $(PYTHON_VERSION) --frozen --all-groups

backend-format:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen ruff format .
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen ruff check . --fix

backend-check:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen ruff format --check .
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen ruff check .
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen mypy app
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen pytest

frontend-install:
	$(NPM) --prefix frontend ci

frontend-check:
	$(NPM) --prefix frontend run lint
	$(NPM) --prefix frontend run typecheck
	$(NPM) --prefix frontend run test
	$(NPM) --prefix frontend run build

frontend-install-docker:
	$(FRONTEND_DOCKER) npm ci

frontend-check-docker: frontend-install-docker
	$(FRONTEND_DOCKER) npm run lint
	$(FRONTEND_DOCKER) npm run typecheck
	$(FRONTEND_DOCKER) npm run test
	$(FRONTEND_DOCKER) npm run build

dev-backend:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen --env-file $(CURDIR)/.env uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	$(NPM) --prefix frontend run dev

dev-frontend-docker: frontend-install-docker
	docker run --rm --user $(PROJECT_UID):$(PROJECT_GID) --add-host host.docker.internal:host-gateway -e npm_config_cache=/tmp/npm-cache -e VITE_PROXY_TARGET=http://host.docker.internal:8000 -p 5173:5173 -v $(CURDIR)/frontend:/app -w /app $(NODE_IMAGE) npm run dev
