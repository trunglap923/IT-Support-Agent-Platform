UV ?= uv
NPM ?= npm
PYTHON_VERSION ?= 3.12
UV_CACHE_DIR ?= /tmp/it-support-agent-uv-cache
NODE_IMAGE ?= node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5
BACKEND_DEV_HOST ?= 0.0.0.0
BACKEND_DEV_PORT ?= 8000
FRONTEND_DEV_PORT ?= 5173
FRONTEND_DEV_CONTAINER ?= it-support-agent-frontend-dev
PROJECT_UID := $(shell id -u)
PROJECT_GID := $(shell id -g)
FRONTEND_DOCKER = docker run --rm --user $(PROJECT_UID):$(PROJECT_GID) -e npm_config_cache=/tmp/npm-cache -v $(CURDIR)/frontend:/app -w /app $(NODE_IMAGE)

.PHONY: help bootstrap check backend-sync backend-format backend-check \
	frontend-install frontend-check frontend-install-docker frontend-check-docker \
	dev-backend dev-frontend dev-frontend-docker dev-stop spike-openai-live \
	spike-mcp-stdio spike-langgraph-postgres eval-validate

help:
	@echo "WP-01 commands:"
	@echo "  make bootstrap              Install locked backend/frontend dependencies"
	@echo "  make check                  Run all checks using host npm"
	@echo "  make backend-check          Format check, lint, typecheck and tests"
	@echo "  make frontend-check         Lint, typecheck, tests and build"
	@echo "  make frontend-check-docker  Same frontend checks with Node 22 in Docker"
	@echo "  make dev-backend            Run FastAPI at http://127.0.0.1:8000"
	@echo "  make dev-frontend           Run Vite at http://127.0.0.1:5173"
	@echo "  make dev-frontend-docker    Run Vite in the managed development container"
	@echo "  make dev-stop               Stop and remove the frontend development container"
	@echo "  make spike-openai-live      Run three small paid Responses API probes (opt-in)"
	@echo "  make spike-mcp-stdio        Verify MCP stdio discovery/call and actor isolation"
	@echo "  make spike-langgraph-postgres  Verify pause/restart/resume (requires CHECKPOINT_DATABASE_URL)"
	@echo "  make eval-validate           Validate the 30 offline M0 evaluation cases"

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
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen --env-file $(CURDIR)/.env uvicorn app.main:app --reload --host $(BACKEND_DEV_HOST) --port $(BACKEND_DEV_PORT)

dev-frontend:
	$(NPM) --prefix frontend run dev

dev-frontend-docker: frontend-install-docker
	@if docker container inspect $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1; then \
		echo "Removing stale container $(FRONTEND_DEV_CONTAINER)..."; \
		docker stop --timeout 5 $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1 || true; \
		docker rm --force $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1 || true; \
	fi
	@port_owner="$$(docker ps --filter publish=$(FRONTEND_DEV_PORT) --format '{{.Names}}')"; \
	if [ -n "$$port_owner" ]; then \
		echo "Port $(FRONTEND_DEV_PORT) is already used by container(s): $$port_owner"; \
		echo "Stop the owning container or choose FRONTEND_DEV_PORT=<another-port>."; \
		exit 1; \
	fi
	@cleanup() { \
		docker stop --timeout 5 $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1 || true; \
		docker rm --force $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1 || true; \
	}; \
	trap 'cleanup; exit 0' HUP INT TERM; \
	trap cleanup EXIT; \
	docker run --detach --rm --init --name $(FRONTEND_DEV_CONTAINER) --user $(PROJECT_UID):$(PROJECT_GID) --add-host host.docker.internal:host-gateway -e npm_config_cache=/tmp/npm-cache -e VITE_PROXY_TARGET=http://host.docker.internal:$(BACKEND_DEV_PORT) -p 127.0.0.1:$(FRONTEND_DEV_PORT):5173 -v $(CURDIR)/frontend:/app -w /app $(NODE_IMAGE) npm run dev >/dev/null; \
	docker logs --follow $(FRONTEND_DEV_CONTAINER)

dev-stop:
	@if docker container inspect $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1; then \
		echo "Stopping and removing $(FRONTEND_DEV_CONTAINER)..."; \
		docker stop --timeout 5 $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1 || true; \
		docker rm --force $(FRONTEND_DEV_CONTAINER) >/dev/null 2>&1 || true; \
	else \
		echo "Frontend development container is not running."; \
	fi

spike-openai-live:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen --env-file $(CURDIR)/.env python -m app.providers.openai_responses_spike

spike-mcp-stdio:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen python -m app.mcp_server.stdio_spike

spike-langgraph-postgres:
	@test -n "$(CHECKPOINT_DATABASE_URL)" || (echo "Set CHECKPOINT_DATABASE_URL to an isolated PostgreSQL database."; exit 1)
	UV_CACHE_DIR=$(UV_CACHE_DIR) LANGGRAPH_STRICT_MSGPACK=true CHECKPOINT_DATABASE_URL="$(CHECKPOINT_DATABASE_URL)" $(UV) --system-certs run --directory backend --frozen python -m app.agent.checkpoint_spike

eval-validate:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --project backend --frozen python -m evals.runner.validate_cases
