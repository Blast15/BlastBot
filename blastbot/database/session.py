from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from blastbot.core.config import Settings
from blastbot.database.base import Base
# Import model modules so every table is registered in Base.metadata before create_all().
from blastbot.database import models as _models  # noqa: F401


class Database:
    def __init__(self, settings: Settings) -> None:
        if settings.is_sqlite:
            raw_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
            if raw_path and raw_path != ":memory:":
                Path(raw_path).parent.mkdir(parents=True, exist_ok=True)

        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=not settings.is_sqlite,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def initialize_schema(self) -> None:
        """Create missing runtime tables and indexes without a separate migration tool."""
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            # These indexes protect ticket invariants on databases upgraded from
            # the legacy bot, where the tables may already exist.
            await connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_tickets_guild_number "
                    "ON tickets (guild_id, number)"
                )
            )
            await connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_tickets_channel_id "
                    "ON tickets (channel_id)"
                )
            )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()
