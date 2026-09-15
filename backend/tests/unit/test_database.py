import asyncio

import pytest

from app.db import Database


def test_database_requires_asyncpg_driver() -> None:
    with pytest.raises(ValueError, match="postgresql\\+asyncpg"):
        Database("postgresql+psycopg://user:password@localhost/example")


def test_database_factory_does_not_connect_until_used() -> None:
    database = Database("postgresql+asyncpg://user:password@127.0.0.1:1/example")

    assert database.engine.url.drivername == "postgresql+asyncpg"
    asyncio.run(database.close())
