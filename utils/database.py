"""Database helper cho SQLite với support thread-safe và transaction handling"""

import asyncio
import json
import logging
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import aiosqlite

from utils.automation_db import AutomationDBMixin
from utils.config import Config
from utils.constants import CACHE_CONFIG
from utils.error_handler import DatabaseError
from utils.ticket_db import TicketDBMixin

logger = logging.getLogger("BlastBot.Database")
if not logger.handlers:
    file_handler = logging.FileHandler("bot.log", encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class AsyncRLock:
    """Asyncio Reentrant Lock cho coroutines.

    Lưu ý: Tính chất reentrant chỉ hoạt động trong cùng một asyncio Task (dựa trên asyncio.current_task()).
    Không truyền lock reentrant qua các task con (e.g., tạo bằng asyncio.create_task hoặc asyncio.gather).
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._owner: asyncio.Task | None = None
        self._count = 0

    async def acquire(self):
        me = asyncio.current_task()
        if self._owner == me:
            self._count += 1
            return
        await self._lock.acquire()
        self._owner = me
        self._count = 1

    async def release(self):
        me = asyncio.current_task()
        if self._owner != me:
            raise RuntimeError("Cannot release un-acquired lock")
        self._count -= 1
        if self._count == 0:
            self._owner = None
            self._lock.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.release()


class LRUCache:
    """Simple LRU Cache implementation with TTL support"""

    def __init__(self, maxsize: int = 128, ttl_seconds: int = 300):
        self.maxsize = maxsize
        self.ttl = timedelta(seconds=ttl_seconds)
        self.cache: OrderedDict[int, dict] = OrderedDict()
        self.timestamps: dict[int, datetime] = {}

    def get(self, key: int) -> dict | None:
        """Get item from cache"""
        if key not in self.cache:
            return None

        # Check if expired
        timestamp = self.timestamps.get(key)
        if timestamp and datetime.now(UTC) - timestamp >= self.ttl:
            self.delete(key)
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key].copy()

    def set(self, key: int, value: dict):
        """Set item in cache"""
        # Remove if exists
        if key in self.cache:
            del self.cache[key]

        # Add new item
        self.cache[key] = value.copy()
        self.timestamps[key] = datetime.now(UTC)

        # Remove oldest if over maxsize
        if len(self.cache) > self.maxsize:
            oldest_key = next(iter(self.cache))
            self.delete(oldest_key)

    def delete(self, key: int):
        """Delete item from cache"""
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]

    def clear(self):
        """Clear all cache"""
        self.cache.clear()
        self.timestamps.clear()

    def get_stats(self) -> dict:
        """Get cache statistics"""
        current_time = datetime.now(UTC)
        valid_entries = sum(
            1
            for key, timestamp in self.timestamps.items()
            if current_time - timestamp < self.ttl
        )

        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self.cache) - valid_entries,
            "maxsize": self.maxsize,
            "ttl_seconds": self.ttl.total_seconds(),
        }


class Database(TicketDBMixin, AutomationDBMixin):
    """Wrapper cho aiosqlite database operations với caching và thread safety"""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or Config.DB_PATH
        self.conn: aiosqlite.Connection | None = None
        self._lock = AsyncRLock()
        self._in_transaction = False
        self._guild_config_cache = LRUCache(
            maxsize=CACHE_CONFIG["guild_config_maxsize"],
            ttl_seconds=CACHE_CONFIG["guild_config_ttl_seconds"],
        )

    @asynccontextmanager
    async def transaction(self):
        """Transaction context manager để gom nhóm nhiều thao tác DB atomic."""
        async with self._lock:
            if not self.conn:
                logger.warning(
                    "Attempted transaction while database connection is closed or not established."
                )
                yield
                return
            was_in_tx = self._in_transaction
            if not was_in_tx:
                self._in_transaction = True
                await self.conn.execute("BEGIN TRANSACTION")
            try:
                yield
                if not was_in_tx:
                    await self.conn.commit()
            except Exception:
                if not was_in_tx:
                    await self.conn.rollback()
                raise
            finally:
                if not was_in_tx:
                    self._in_transaction = False

    async def _commit_if_not_in_tx(self):
        if not self._in_transaction and self.conn:
            await self.conn.commit()

    async def connect(self) -> None:
        """Kết nối đến database và cấu hình PRAGMA."""
        async with self._lock:
            try:
                self.conn = await aiosqlite.connect(self.db_path)
                self.conn.row_factory = aiosqlite.Row
                await self.conn.execute("PRAGMA foreign_keys = ON")
                await self.conn.execute("PRAGMA journal_mode = WAL")
                await self.conn.execute("PRAGMA busy_timeout = 5000")
                await self._initialize_tables_internal()
                logger.info(f"Database connected: {self.db_path}")
            except aiosqlite.Error as e:
                logger.error(f"Failed to connect to database: {e}")
                raise DatabaseError(f"Database connection failed: {e}")

    async def close(self):
        """Đóng kết nối database"""
        async with self._lock:
            if self.conn:
                try:
                    await self.conn.close()
                    self.conn = None
                    logger.info("Database connection closed")
                except aiosqlite.Error as e:
                    logger.error(f"Error closing database: {e}")

    async def _get_schema_version(self) -> int:
        if not self.conn:
            return 0
        async with self.conn.execute("PRAGMA user_version") as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def _set_schema_version(self, version: int) -> None:
        if self.conn:
            await self.conn.execute(f"PRAGMA user_version = {version}")

    async def initialize_tables(self):
        async with self._lock:
            await self.run_migrations()

    async def _initialize_tables_internal(self):
        await self.run_migrations()

    async def run_migrations(self):
        if not self.conn:
            return

        version = await self._get_schema_version()
        try:
            if version < 1:
                await self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS guilds (
                        guild_id INTEGER PRIMARY KEY,
                        welcome_channel_id INTEGER,
                        log_channel_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        warnings INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (guild_id, user_id)
                    )
                """)

                await self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS role_menus (
                        message_id INTEGER PRIMARY KEY,
                        guild_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        role_ids TEXT NOT NULL,
                        mode TEXT NOT NULL DEFAULT 'toggle',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
                    )
                """)

                await self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS suggestion_votes (
                        message_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        vote INTEGER NOT NULL,
                        PRIMARY KEY (message_id, user_id)
                    )
                """)

                await self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS suggestion_messages (
                        guild_id INTEGER NOT NULL,
                        message_id INTEGER NOT NULL,
                        PRIMARY KEY (message_id)
                    )
                """)

                await self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS moderation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        moderator_id INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        target_id INTEGER NOT NULL,
                        target_str TEXT,
                        reason TEXT,
                        extra_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS temp_roles (
                        guild_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        role_id INTEGER NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        PRIMARY KEY (guild_id, user_id, role_id)
                    )
                """)

                await self.init_ticket_tables()
                await self.init_automation_tables()
                version = 1
                await self._set_schema_version(version)

            await self._commit_if_not_in_tx()
            logger.info(f"Database schema up to date (version {version})")
        except aiosqlite.Error as e:
            logger.error(f"Failed to run database migrations: {e}")
            raise DatabaseError(f"Database migration failed: {e}")

    async def register_suggestion_message(self, guild_id: int, message_id: int):
        async with self._lock:
            if not self.conn:
                return

            await self.conn.execute(
                """
                INSERT OR IGNORE INTO suggestion_messages (guild_id, message_id)
                VALUES (?, ?)
                """,
                (guild_id, message_id),
            )
            await self._commit_if_not_in_tx()

    async def get_suggestion_messages(self) -> list[int]:
        async with self._lock:
            if not self.conn:
                return []

            async with self.conn.execute(
                "SELECT message_id FROM suggestion_messages"
            ) as cursor:
                rows = await cursor.fetchall()
            return [row["message_id"] for row in rows]

    async def set_vote(self, message_id: int, user_id: int, vote: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                """
                INSERT INTO suggestion_votes (message_id, user_id, vote)
                VALUES (?, ?, ?)
                ON CONFLICT(message_id, user_id) DO UPDATE SET vote = excluded.vote
                """,
                (message_id, user_id, vote),
            )
            await self._commit_if_not_in_tx()

    async def remove_vote(self, message_id: int, user_id: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "DELETE FROM suggestion_votes WHERE message_id = ? AND user_id = ?",
                (message_id, user_id),
            )
            await self._commit_if_not_in_tx()

    async def get_vote_counts(self, message_id: int) -> tuple[int, int]:
        async with self._lock:
            if not self.conn:
                return (0, 0)
            async with self.conn.execute(
                "SELECT vote, COUNT(*) AS c FROM suggestion_votes WHERE message_id = ? GROUP BY vote",
                (message_id,),
            ) as cursor:
                rows = await cursor.fetchall()
            up = down = 0
            for row in rows:
                if row["vote"] == 1:
                    up = row["c"]
                elif row["vote"] == -1:
                    down = row["c"]
            return (up, down)

    async def get_user_vote(self, message_id: int, user_id: int) -> int | None:
        async with self._lock:
            if not self.conn:
                return None
            async with self.conn.execute(
                "SELECT vote FROM suggestion_votes WHERE message_id = ? AND user_id = ?",
                (message_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()
            return row["vote"] if row else None

    async def add_mod_log(
        self,
        guild_id: int,
        moderator_id: int,
        action: str,
        target_id: int,
        target_str: str | None,
        reason: str | None,
        **extra,
    ):
        async with self._lock:
            if not self.conn:
                return

            extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
            await self.conn.execute(
                """
                INSERT INTO moderation_logs (
                    guild_id, moderator_id, action, target_id, target_str, reason, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    moderator_id,
                    action,
                    target_id,
                    target_str,
                    reason,
                    extra_json,
                ),
            )
            await self._commit_if_not_in_tx()

    async def get_guild_config(self, guild_id: int) -> dict:
        async with self._lock:
            cached_config = self._guild_config_cache.get(guild_id)
            if cached_config is not None:
                logger.debug(f"Cache hit for guild {guild_id}")
                return cached_config

            default_config = {
                "guild_id": guild_id,
                "welcome_channel_id": None,
                "log_channel_id": None,
            }

            if not self.conn:
                return default_config.copy()

            try:
                async with self.conn.execute(
                    "SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        config = dict(row)
                        self._guild_config_cache.set(guild_id, config)
                        return config.copy()
                    else:
                        await self.conn.execute(
                            "INSERT INTO guilds (guild_id) VALUES (?)", (guild_id,)
                        )
                        await self._commit_if_not_in_tx()
                        self._guild_config_cache.set(guild_id, default_config)
                        return default_config.copy()
            except aiosqlite.Error as e:
                logger.error(f"Failed to get guild config for {guild_id}: {e}")
                return default_config.copy()

    async def update_guild_config(self, guild_id: int, **kwargs):
        async with self._lock:
            if not self.conn:
                return

            valid_fields = ["welcome_channel_id", "log_channel_id"]
            updates = {k: v for k, v in kwargs.items() if k in valid_fields}

            if not updates:
                return

            try:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", (guild_id,)
                )
                set_clause = ", ".join([f"{k} = ?" for k in updates])
                values = list(updates.values()) + [guild_id]

                await self.conn.execute(
                    f"UPDATE guilds SET {set_clause} WHERE guild_id = ?", values
                )
                await self._commit_if_not_in_tx()
                self.invalidate_cache(guild_id)
                logger.debug(f"Updated guild config for {guild_id}: {updates}")
            except aiosqlite.Error as e:
                logger.error(f"Failed to update guild config for {guild_id}: {e}")
                if not self._in_transaction:
                    await self.conn.rollback()
                raise DatabaseError(f"Failed to update guild config: {e}")

    def invalidate_cache(self, guild_id: int | None = None):
        if guild_id is None:
            self._guild_config_cache.clear()
            logger.debug("Cleared all guild config cache")
        else:
            self._guild_config_cache.delete(guild_id)
            logger.debug(f"Invalidated cache for guild {guild_id}")

    def get_cache_stats(self) -> dict:
        return self._guild_config_cache.get_stats()

    async def get_user_data(self, user_id: int, guild_id: int) -> dict:
        async with self._lock:
            default_data = {
                "user_id": user_id,
                "guild_id": guild_id,
                "warnings": 0,
            }

            if not self.conn:
                return default_data

            try:
                async with self.conn.execute(
                    "SELECT guild_id, user_id, warnings FROM users WHERE user_id = ? AND guild_id = ?",
                    (user_id, guild_id),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)

                    await self.conn.execute(
                        "INSERT INTO users (guild_id, user_id, warnings) VALUES (?, ?, 0)",
                        (guild_id, user_id),
                    )
                    await self._commit_if_not_in_tx()
                    return default_data
            except aiosqlite.Error as e:
                logger.error(
                    f"Failed to get user data for {user_id} in guild {guild_id}: {e}"
                )
                return default_data

    async def update_user_data(self, user_id: int, guild_id: int, **kwargs):
        async with self._lock:
            if not self.conn:
                return

            valid_fields = ["warnings"]
            updates = {k: v for k, v in kwargs.items() if k in valid_fields}

            if not updates:
                return

            try:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)",
                    (guild_id, user_id),
                )
                set_clause = ", ".join([f"{k} = ?" for k in updates])
                values = list(updates.values()) + [guild_id, user_id]

                await self.conn.execute(
                    f"UPDATE users SET {set_clause} WHERE guild_id = ? AND user_id = ?",
                    values,
                )
                await self._commit_if_not_in_tx()
                logger.debug(
                    f"Updated user data for {user_id} in guild {guild_id}: {updates}"
                )
            except aiosqlite.Error as e:
                logger.error(
                    f"Failed to update user data for {user_id} in guild {guild_id}: {e}"
                )
                if not self._in_transaction:
                    await self.conn.rollback()
                raise DatabaseError(f"Failed to update user data: {e}")

    async def add_warning(self, guild_id: int, user_id: int) -> int:
        async with self._lock:
            if not self.conn:
                return 0

            await self.conn.execute(
                """
                INSERT INTO users (guild_id, user_id, warnings)
                VALUES (?, ?, 1)
                ON CONFLICT(guild_id, user_id)
                DO UPDATE SET warnings = warnings + 1
                """,
                (guild_id, user_id),
            )
            await self._commit_if_not_in_tx()

            async with self.conn.execute(
                "SELECT warnings FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ) as cur:
                row = await cur.fetchone()
            return row[0] if row else 0

    async def get_warnings(self, guild_id: int, user_id: int) -> int:
        async with self._lock:
            if not self.conn:
                return 0

            async with self.conn.execute(
                "SELECT warnings FROM users WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ) as cur:
                row = await cur.fetchone()
            return row[0] if row else 0

    async def add_temp_role(
        self, guild_id: int, user_id: int, role_id: int, expires_at: datetime
    ):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                """
                INSERT INTO temp_roles (guild_id, user_id, role_id, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, role_id)
                DO UPDATE SET expires_at = excluded.expires_at
                """,
                (guild_id, user_id, role_id, expires_at.isoformat()),
            )
            await self._commit_if_not_in_tx()

    async def remove_temp_role(self, guild_id: int, user_id: int, role_id: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "DELETE FROM temp_roles WHERE guild_id = ? AND user_id = ? AND role_id = ?",
                (guild_id, user_id, role_id),
            )
            await self._commit_if_not_in_tx()

    async def get_expired_temp_roles(self) -> list[dict]:
        async with self._lock:
            if not self.conn:
                return []
            now = datetime.now(UTC).isoformat()
            async with self.conn.execute(
                "SELECT * FROM temp_roles WHERE expires_at <= ?", (now,)
            ) as cursor:
                rows = await cursor.fetchall()
            return [dict(row) for row in rows]
