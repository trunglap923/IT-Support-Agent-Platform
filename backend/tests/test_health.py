import asyncio

from httpx2 import ASGITransport, AsyncClient

from app.config import AppEnvironment, Settings
from app.main import create_app


def test_liveness_uses_fake_provider_without_external_services() -> None:
    async def run() -> None:
        settings = Settings(app_env=AppEnvironment.TEST)
        app = create_app(settings=settings)
        transport = ASGITransport(app=app)

        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            response = await client.get("/api/v1/health/live")
            readiness = await client.get("/api/v1/health/ready")

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]
        assert response.json() == {
            "status": "ok",
            "service": "IT Support Agent Platform",
            "version": "0.1.0",
            "environment": "test",
            "provider": "fake",
            "request_id": response.headers["X-Request-ID"],
        }
        assert readiness.status_code == 503
        assert readiness.json() == {
            "status": "not_ready",
            "dependencies": {
                "postgres": "not_configured",
                "redis": "not_configured",
            },
        }

    asyncio.run(run())
