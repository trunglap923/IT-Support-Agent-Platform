"""Process-local async SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Own an engine created inside the current process/event-loop lifecycle."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session without hiding transaction or commit boundaries."""

        async with self.session_factory() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()

    async def ping(self) -> None:
        """Verify that the process can execute a minimal database query."""

        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
