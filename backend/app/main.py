"""FastAPI application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.config import Settings
from app.db import Database
from app.providers import TextGenerationProvider, create_provider
from app.request_id import RequestIdMiddleware


def create_app(
    settings: Settings | None = None,
    provider: TextGenerationProvider | None = None,
    database: Database | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resolved_provider = provider or create_provider(resolved_settings)
        resolved_database = database
        if resolved_database is None and resolved_settings.database_url is not None:
            resolved_database = Database(resolved_settings.database_url.get_secret_value())
        application.state.provider = resolved_provider
        application.state.database = resolved_database
        try:
            yield
        finally:
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
    application.include_router(runs_router, prefix="/api/v1")
    return application


app = create_app()
