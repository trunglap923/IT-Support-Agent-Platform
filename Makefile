UV ?= uv
NPM ?= npm
PYTHON_VERSION ?= 3.12
UV_CACHE_DIR ?= /tmp/it-support-agent-uv-cache
NODE_IMAGE ?= node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5
PLAYWRIGHT_IMAGE ?= mcr.microsoft.com/playwright:v1.63.0-noble
BACKEND_DEV_HOST ?= 0.0.0.0
BACKEND_DEV_PORT ?= 8000
FRONTEND_DEV_PORT ?= 5173
FRONTEND_DEV_CONTAINER ?= it-support-agent-frontend-dev
COMPOSE ?= docker compose
COMPOSE_FILE ?= $(CURDIR)/infra/compose.yaml
COMPOSE_ENV_FILE ?= $(CURDIR)/.env
COMPOSE_OPS_FILE ?= $(CURDIR)/infra/compose.ops.yaml
STACK_COMPOSE = $(COMPOSE) --file $(COMPOSE_FILE) --env-file $(COMPOSE_ENV_FILE)
OPS_COMPOSE = $(COMPOSE) --file $(COMPOSE_FILE) --file $(COMPOSE_OPS_FILE) --env-file $(COMPOSE_ENV_FILE)
PROJECT_UID := $(shell id -u)
PROJECT_GID := $(shell id -g)
FRONTEND_DOCKER = docker run --rm --user $(PROJECT_UID):$(PROJECT_GID) -e npm_config_cache=/tmp/npm-cache -v $(CURDIR)/frontend:/app -w /app $(NODE_IMAGE)

.PHONY: help bootstrap bootstrap-host env-init stack-build up down status test \
	test-e2e eval demo clean-verify backup restore-test docs-check check backend-sync backend-format backend-check \
	frontend-install frontend-check frontend-install-docker frontend-check-docker \
	frontend-e2e-docker \
	dev-backend dev-frontend dev-frontend-docker dev-stop spike-openai-live \
	spike-mcp-stdio spike-langgraph-postgres eval-validate eval-agent-fake \
	eval-agent-repro eval-agent-live knowledge-validate knowledge-reindex \
	knowledge-reindex-dry-run retrieval-baseline \
	wp13-gate-tests quality-report \
	db-up db-down db-status redis-up redis-down redis-status services-up services-down \
	migrate seed seed-dry-run seed-demo-user wp02-integration-check wp03-integration-check \
	wp10-integration-check backend-integration-check wp02-check wp03-check \
	wp12-integration-check wp12-check worker-agent worker-background scheduler

help:
	@echo "Primary reproducible commands:"
	@echo "  make bootstrap              Create local env if needed and build locked images"
	@echo "  make up                     Build/start the complete seven-service stack"
	@echo "  make migrate                Run Alembic as an explicit one-shot container"
	@echo "  make seed                   Seed business scenarios and published IT knowledge"
	@echo "  make seed-dry-run           Validate and preview seed changes without persisting"
	@echo "  make test                   Run backend tests with isolated DB/Redis, then frontend checks"
	@echo "  make test-e2e               Run browser E2E in pinned Playwright"
	@echo "  make eval                   Run the deterministic, non-paid evaluation"
	@echo "  make demo                   Migrate, seed and start the complete demo stack"
	@echo "  make down                   Stop the stack while preserving all named volumes"
	@echo "  make clean-verify           Verify build/migrate/seed/health in an isolated project"
	@echo "  make backup                 Back up PostgreSQL and document storage with checksums"
	@echo "  make restore-test           Restore the latest backup into isolated temporary targets"
	@echo "  make docs-check             Validate tracked relative Markdown links"
	@echo "Developer commands:"
	@echo "  make bootstrap-host         Install locked backend/frontend host dependencies"
	@echo "  make check                  Run all checks using host npm"
	@echo "  make backend-check          Format check, lint, typecheck and tests"
	@echo "  make frontend-check         Lint, typecheck, tests and build"
	@echo "  make frontend-check-docker  Same frontend checks with Node 22 in Docker"
	@echo "  make frontend-e2e-docker    Run ticket/approval browser tests in pinned Playwright"
	@echo "  make dev-backend            Run FastAPI at http://127.0.0.1:8000"
	@echo "  make dev-frontend           Run Vite at http://127.0.0.1:5173"
	@echo "  make dev-frontend-docker    Run Vite in the managed development container"
	@echo "  make dev-stop               Stop and remove the frontend development container"
	@echo "  make spike-openai-live      Run three small paid Responses API probes (opt-in)"
	@echo "  make spike-mcp-stdio        Verify MCP stdio discovery/call and actor isolation"
	@echo "  make spike-langgraph-postgres  Verify pause/restart/resume (requires CHECKPOINT_DATABASE_URL)"
	@echo "  make eval-validate           Validate all 120 versioned evaluation cases"
	@echo "  make eval-agent-fake         Run deterministic development-split evaluation"
	@echo "  make eval-agent-repro        Verify identical fake runs have the same digest"
	@echo "  make eval-agent-live         Run 1 RAG case 3 times (paid and explicit opt-in)"
	@echo "  make wp13-gate-tests         Run PostgreSQL-backed G-01/G-02/G-03/G-08 regressions"
	@echo "  make quality-report          Generate reviewed G-01..G-09/performance/cost reports"
	@echo "  make knowledge-validate      Validate corpus metadata, ACL rules and checksums"
	@echo "  make knowledge-reindex-dry-run  Preview seed-corpus embedding changes"
	@echo "  make knowledge-reindex       Re-embed only seed-corpus versions (paid opt-in guarded)"
	@echo "  make retrieval-baseline      Run isolated PostgreSQL retrieval evaluation"
	@echo "  make db-up                  Start local PostgreSQL/pgvector and wait until healthy"
	@echo "  make db-down                Stop containers; preserve the PostgreSQL volume"
	@echo "  make db-status              Show local Compose service status"
	@echo "  make redis-up               Start local Redis and wait until healthy"
	@echo "  make redis-down             Stop local Redis; preserve its volume"
	@echo "  make redis-status           Show local Redis service status"
	@echo "  make services-up            Start PostgreSQL and Redis"
	@echo "  make services-down          Stop all local Compose services; preserve volumes"
	@echo "  make worker-agent           Run the agent queue worker (concurrency 2 by default)"
	@echo "  make worker-background      Run the background queue worker"
	@echo "  make scheduler              Run the single development Celery beat scheduler"
	@echo "  make migrate                Upgrade the configured application database"
	@echo "  make seed-demo-user         Compatibility alias for the complete demo seed"
	@echo "  make wp02-integration-check  Run DB/migration/auth/ownership tests in isolated databases"
	@echo "  make wp03-integration-check  Run run-state/enqueue/SSE/Redis service integration tests"
	@echo "  make wp10-integration-check  Run MCP/approval/ticket/recovery integration tests"
	@echo "  make wp12-integration-check  Run memory consent/device/epoch integration tests"
	@echo "  make backend-integration-check  Run all service integration tests"
	@echo "  make wp02-check             Run all WP-02 backend and frontend checks"
	@echo "  make wp03-check             Run all WP-03 backend, service and frontend checks"

bootstrap: env-init stack-build

bootstrap-host: backend-sync frontend-install

env-init:
	@if [ ! -f "$(COMPOSE_ENV_FILE)" ]; then \
		cp "$(CURDIR)/.env.example" "$(COMPOSE_ENV_FILE)"; \
		echo "Created .env from .env.example; set DEMO_SEED_PASSWORD before make seed."; \
	fi
	@$(COMPOSE) version >/dev/null
	@$(STACK_COMPOSE) config --quiet

stack-build: env-init
	$(STACK_COMPOSE) build api frontend

up: env-init
	$(STACK_COMPOSE) up --detach --build --wait

down:
	$(STACK_COMPOSE) down

status:
	$(STACK_COMPOSE) ps

test: env-init
	bash $(CURDIR)/infra/scripts/run-tests.sh

test-e2e: frontend-e2e-docker

eval: env-init
	bash $(CURDIR)/infra/scripts/run-eval.sh

demo: migrate seed up
	@echo "Demo ready at http://127.0.0.1:$${FRONTEND_PORT:-5173}"

clean-verify:
	bash $(CURDIR)/infra/scripts/clean-verify.sh

backup: env-init
	bash $(CURDIR)/infra/scripts/backup.sh

restore-test: env-init
	BACKUP_DIR="$(BACKUP_DIR)" bash $(CURDIR)/infra/scripts/restore-test.sh

docs-check:
	python3 $(CURDIR)/infra/scripts/check_markdown_links.py

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

wp02-integration-check:
	RUN_FRONTEND=0 bash $(CURDIR)/infra/scripts/run-tests.sh /app/tests/integration/test_migrations.py /app/tests/integration/test_user_repository.py /app/tests/integration/test_auth_api.py /app/tests/integration/test_conversation_ownership.py

wp03-integration-check:
	RUN_FRONTEND=0 bash $(CURDIR)/infra/scripts/run-tests.sh /app/tests/integration/test_run_state_store.py /app/tests/integration/test_run_enqueue.py /app/tests/integration/test_sse_api.py /app/tests/integration/test_redis_dispatch.py /app/tests/integration/test_health_readiness.py /app/tests/integration/test_auth_rate_limit.py

wp10-integration-check:
	RUN_FRONTEND=0 bash $(CURDIR)/infra/scripts/run-tests.sh /app/tests/integration/test_business_reads.py /app/tests/integration/test_mcp_business_reads.py /app/tests/integration/test_approval_lifecycle.py /app/tests/integration/test_approval_checkpoint_resume.py /app/tests/integration/test_ticket_api.py /app/tests/integration/test_ticket_write.py /app/tests/integration/test_operations_api.py /app/tests/integration/test_redis_dispatch.py /app/tests/integration/test_workflow_recovery.py /app/tests/integration/test_workflow_failure_recovery.py

wp12-integration-check:
	RUN_FRONTEND=0 bash $(CURDIR)/infra/scripts/run-tests.sh /app/tests/integration/test_migrations.py /app/tests/integration/test_consent_memory.py /app/tests/integration/test_cross_conversation_memory.py /app/tests/integration/test_memory_concurrency.py

backend-integration-check:
	RUN_FRONTEND=0 bash $(CURDIR)/infra/scripts/run-tests.sh /app/tests/integration

wp02-check: backend-check wp02-integration-check frontend-check-docker

wp03-check: backend-check wp03-integration-check frontend-check-docker

wp12-check: backend-check wp12-integration-check frontend-check-docker frontend-e2e-docker

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

frontend-e2e-docker: frontend-install-docker
	docker run --rm --ipc=host --user $(PROJECT_UID):$(PROJECT_GID) -e npm_config_cache=/tmp/npm-cache -v $(CURDIR)/frontend:/app -w /app $(PLAYWRIGHT_IMAGE) npm run test:e2e

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

eval-agent-fake: eval-validate
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --project backend --frozen python -m evals.runner.cli --mode fake --split development --output reports/raw/agent-evaluation-fake.json

eval-agent-repro: eval-validate
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --project backend --frozen python -m evals.runner.repro_check

eval-agent-live: eval-validate
	@test "$${RUN_LIVE_EVAL:-0}" = "1" || (echo "Set RUN_LIVE_EVAL=1 to authorize paid evaluation."; exit 1)
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --project backend --frozen --env-file $(COMPOSE_ENV_FILE) python -m evals.runner.cli --mode live --split development --category rag --max-cases 1 --repetitions 3 --output reports/raw/agent-evaluation-live.json

knowledge-validate:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen python ../data/manifests/validate_corpus.py

retrieval-baseline:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --project backend --frozen --env-file $(COMPOSE_ENV_FILE) python -m evals.runner.retrieval_baseline

wp13-gate-tests:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --project backend --frozen --env-file $(COMPOSE_ENV_FILE) python -m evals.runner.gate_tests

quality-report: eval-agent-fake wp13-gate-tests retrieval-baseline
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --project backend --frozen python -m evals.runner.quality_report

db-up:
	$(STACK_COMPOSE) up --detach --wait postgres

db-down:
	$(STACK_COMPOSE) stop postgres

db-status:
	$(STACK_COMPOSE) ps

redis-up:
	$(STACK_COMPOSE) up --detach --wait redis

redis-down:
	$(STACK_COMPOSE) stop redis

redis-status:
	$(STACK_COMPOSE) ps redis

services-up:
	$(STACK_COMPOSE) up --detach --wait postgres redis

services-down:
	$(STACK_COMPOSE) down

worker-agent:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen --env-file $(COMPOSE_ENV_FILE) celery -A app.jobs.celery_app:celery_app worker --queues agent --concurrency $${CELERY_AGENT_CONCURRENCY:-2} --loglevel INFO

worker-background:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen --env-file $(COMPOSE_ENV_FILE) celery -A app.jobs.celery_app:celery_app worker --queues background --concurrency $${CELERY_BACKGROUND_CONCURRENCY:-1} --loglevel INFO

scheduler:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) --system-certs run --directory backend --frozen --env-file $(COMPOSE_ENV_FILE) celery -A app.jobs.celery_app:celery_app beat --loglevel INFO

migrate: env-init
	$(STACK_COMPOSE) build api
	$(STACK_COMPOSE) up --detach --wait postgres redis
	$(OPS_COMPOSE) run --rm migrate

seed: env-init
	$(STACK_COMPOSE) build api
	$(STACK_COMPOSE) up --detach --wait postgres redis
	$(STACK_COMPOSE) run --rm --no-deps api python -m app.demo_seed_command

seed-dry-run: env-init
	$(STACK_COMPOSE) build api
	$(STACK_COMPOSE) up --detach --wait postgres redis
	$(STACK_COMPOSE) run --rm --no-deps api python -m app.demo_seed_command --dry-run

seed-demo-user: seed

knowledge-reindex-dry-run: env-init
	$(STACK_COMPOSE) build api
	$(STACK_COMPOSE) up --detach --wait postgres redis
	$(STACK_COMPOSE) run --rm --no-deps api python -m app.knowledge_reindex --dry-run

knowledge-reindex: env-init
	$(STACK_COMPOSE) build api
	$(STACK_COMPOSE) up --detach --wait postgres redis
	$(STACK_COMPOSE) run --rm --no-deps api python -m app.knowledge_reindex
