from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from blastbot.core.config import Settings

# Import model modules so every table is registered in Base.metadata before create_all().
from blastbot.database import models as _models  # noqa: F401
from blastbot.database.base import Base


class Database:
    SCHEMA_VERSION = 2

    def __init__(self, settings: Settings) -> None:
        if settings.is_sqlite:
            raw_path = settings.database_url.removeprefix("sqlite+aiosqlite:///")
            if raw_path and raw_path != ":memory:":
                Path(raw_path).parent.mkdir(parents=True, exist_ok=True)

        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            pool_pre_ping=not settings.is_sqlite,
            connect_args={"timeout": 30} if settings.is_sqlite else {},
        )
        if settings.is_sqlite:

            @event.listens_for(self.engine.sync_engine, "connect")
            def configure_sqlite(connection: object, _: object) -> None:
                cursor = connection.cursor()  # type: ignore[attr-defined]
                try:
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.execute("PRAGMA busy_timeout=30000")
                finally:
                    cursor.close()

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def initialize_schema(self) -> None:
        """Apply ordered, idempotent schema migrations in one startup transaction."""
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations ("
                    "version INTEGER PRIMARY KEY, "
                    "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
            )
            applied = set(
                await connection.scalars(text("SELECT version FROM schema_migrations"))
            )
            migrations = (self._migration_create_schema, self._migration_reddit_images_only)
            if len(migrations) != self.SCHEMA_VERSION:
                raise RuntimeError("SCHEMA_VERSION does not match registered migrations")
            for version, migration in enumerate(migrations, start=1):
                if version in applied:
                    continue
                await migration(connection)
                await connection.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                    {"version": version},
                )

    @staticmethod
    async def _migration_create_schema(connection: AsyncConnection) -> None:
        await connection.run_sync(Base.metadata.create_all)

    @staticmethod
    async def _migration_reddit_images_only(connection: AsyncConnection) -> None:
        reddit_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"]
                for column in inspect(sync_connection).get_columns("reddit_subscriptions")
            }
        )
        if "images_only" not in reddit_columns:
            await connection.execute(
                text(
                    "ALTER TABLE reddit_subscriptions "
                    "ADD COLUMN images_only BOOLEAN NOT NULL DEFAULT FALSE"
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
