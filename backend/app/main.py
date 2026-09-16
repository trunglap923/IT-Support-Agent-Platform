"""FastAPI application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.approvals import router as approvals_router
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.api.tickets import router as tickets_router
from app.config import Settings
from app.db import Database
from app.jobs.celery_app import celery_app
from app.jobs.dispatch import CeleryRunDispatcher, RunDispatcher, UnavailableRunDispatcher
from app.observability import create_ai_observer
from app.providers import StructuredResponseProvider, create_provider
from app.request_id import RequestIdMiddleware


def create_app(
    settings: Settings | None = None,
    provider: StructuredResponseProvider | None = None,
    database: Database | None = None,
    redis_client: Redis | None = None,
    run_dispatcher: RunDispatcher | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resolved_database = database
        if resolved_database is None and resolved_settings.database_url is not None:
            resolved_database = Database(resolved_settings.database_url.get_secret_value())
        resolved_provider = provider or create_provider(resolved_settings, resolved_database)
        observer = create_ai_observer(resolved_settings)
        resolved_redis = redis_client
        if resolved_redis is None and resolved_settings.redis_url is not None:
            resolved_redis = Redis.from_url(
                resolved_settings.redis_url.get_secret_value(),
                socket_connect_timeout=resolved_settings.redis_socket_timeout_seconds,
                socket_timeout=resolved_settings.redis_socket_timeout_seconds,
            )
        application.state.provider = resolved_provider
        application.state.database = resolved_database
        application.state.redis = resolved_redis
        application.state.run_dispatcher = run_dispatcher or (
            CeleryRunDispatcher(
                celery_app,
                redis_url=resolved_settings.redis_url.get_secret_value(),
                socket_timeout_seconds=resolved_settings.redis_socket_timeout_seconds,
            )
            if resolved_settings.redis_url is not None
            else UnavailableRunDispatcher()
        )
        application.state.ai_observer = observer
        try:
            yield
        finally:
            observer.close()
            if resolved_redis is not None:
                await resolved_redis.aclose()
            if resolved_database is not None:
                await resolved_database.close()
            await resolved_provider.close()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.add_middleware(RequestIdMiddleware)
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(approvals_router, prefix="/api/v1")
    application.include_router(conversations_router, prefix="/api/v1")
    application.include_router(runs_router, prefix="/api/v1")
    application.include_router(tickets_router, prefix="/api/v1")
    return application


app = create_app()
