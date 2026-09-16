from fastapi.testclient import TestClient

from app.config import AppEnvironment, Settings
from app.main import create_app


def test_readiness_uses_real_postgres_and_redis(
    migrated_database_url: str,
    test_redis_url: str,
) -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_url=migrated_database_url,
        redis_url=test_redis_url,
    )

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"postgres": "up", "redis": "up"},
    }
