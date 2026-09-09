from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import event, func, select, text

from blastbot.core.config import Settings
from blastbot.core.context import build_context
from blastbot.core.errors import ConflictError, PermissionDeniedError, ValidationError
from blastbot.database.models import ModerationLog
from blastbot.database.session import Database
from blastbot.modules.automation.cog import AutomationCog, render_greeting
from blastbot.modules.automation.service import validate_greeting_template
from blastbot.modules.moderation.service import ModerationRecord
from blastbot.shared.time import ensure_utc


def settings(database_url: str) -> Settings:
    return Settings(
        DISCORD_TOKEN="x" * 40,
        DATABASE_URL=database_url,
        OWNER_ID="",
        DEV_GUILD_ID="",
        REDDIT_CLIENT_ID="",
        REDDIT_CLIENT_SECRET="",
        REDDIT_KEYLESS_FALLBACK=False,
    )


class GreetingTests(unittest.TestCase):
    def setUp(self) -> None:
        guild = SimpleNamespace(name="Blast", member_count=42)
        self.member = SimpleNamespace(
            mention="<@1>", display_name="Tester", guild=guild
        )
        self.member.__str__ = lambda _: "tester#0001"

    def test_valid_placeholders_render(self) -> None:
        result = render_greeting(
            "{user_mention} {user_name} {server} {member_count} {user}", self.member
        )
        self.assertIn("<@1> Tester Blast 42", result)

    def test_greeting_rejects_unknown_placeholder(self) -> None:
        with self.assertRaises(ValidationError):
            validate_greeting_template("{unknown}", maximum=2000)

    def test_greeting_rejects_format_spec_amplification(self) -> None:
        with self.assertRaises(ValidationError):
            validate_greeting_template("{server:>100000000}", maximum=2000)

    def test_greeting_rejects_conversion(self) -> None:
        with self.assertRaises(ValidationError):
            validate_greeting_template("{user!r}", maximum=2000)

    def test_greeting_output_limit(self) -> None:
        member = SimpleNamespace(
            mention="<@1>",
            display_name="x" * 4000,
            guild=SimpleNamespace(name="Blast", member_count=1),
        )
        row = SimpleNamespace(
            message="{user_name}", use_embed=False, kind="welcome", title=None, color=None
        )
        cog = object.__new__(AutomationCog)
        with self.assertRaises(ValidationError):
            asyncio.run(cog._send_greeting(SimpleNamespace(), member, row))

    def test_malformed_legacy_greeting_does_not_crash_listener(self) -> None:
        channel = SimpleNamespace(send=AsyncMock())
        row = SimpleNamespace(
            message="{server:>100000000}",
            use_embed=False,
            kind="welcome",
            title=None,
            color=None,
            enabled=True,
            channel_id=10,
        )
        guild = SimpleNamespace(
            id=1,
            name="Blast",
            member_count=1,
            get_channel=lambda _: channel,
        )
        member = SimpleNamespace(
            id=2,
            bot=False,
            mention="<@2>",
            display_name="Member",
            guild=guild,
        )
        cog = object.__new__(AutomationCog)
        cog.bot = SimpleNamespace(
            app=SimpleNamespace(
                automation_repo=SimpleNamespace(get_greeting=AsyncMock(return_value=row))
            )
        )
        with patch("blastbot.modules.automation.cog.discord.TextChannel", object):
            asyncio.run(cog.on_member_join(member))
        channel.send.assert_not_awaited()


class DatabaseReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        path = Path(self.tempdir.name) / "test.db"
        self.app = await build_context(settings(f"sqlite+aiosqlite:///{path}"))

    async def asyncTearDown(self) -> None:
        await self.app.database.dispose()
        self.tempdir.cleanup()

    async def test_delivery_updates_use_one_statement_and_preserve_scope(self) -> None:
        reddit_id = await self.app.reddit.add(1, 10, "python")
        auto_id = await self.app.automation.add_auto_message(
            guild_id=1, channel_id=10, content="message", interval_minutes=5, use_embed=False
        )
        now = datetime.now(UTC)
        statements = []

        def record(_conn, _cursor, statement, _parameters, _context, _many) -> None:
            statements.append(statement)

        reddit = self.app.reddit_repo
        automation = self.app.automation_repo
        cases = (
            (reddit.set_enabled, (1, reddit_id, False), True),
            (reddit.set_enabled, (1, reddit_id, False), True),
            (reddit.set_enabled, (2, reddit_id, True), False),
            (reddit.set_enabled, (1, reddit_id + 1, True), False),
            (automation.toggle_auto_message, (1, auto_id, False), True),
            (automation.toggle_auto_message, (1, auto_id, False), True),
            (automation.toggle_auto_message, (2, auto_id, True), False),
            (automation.toggle_auto_message, (1, auto_id + 1, True), False),
            (reddit.mark_seen, (reddit_id, "new-post"), None),
            (reddit.mark_seen, (reddit_id + 1, "missing"), None),
            (automation.mark_sent, (auto_id, now), None),
            (automation.mark_sent, (auto_id + 1, now), None),
        )
        engine = self.app.database.engine.sync_engine
        event.listen(engine, "before_cursor_execute", record)
        try:
            for method, args, expected in cases:
                with self.subTest(method=method.__name__, args=args):
                    statements.clear()
                    self.assertEqual(await method(*args), expected)
                    self.assertEqual(len(statements), 1, statements)
                    self.assertTrue(statements[0].startswith("UPDATE "), statements)
        finally:
            event.remove(engine, "before_cursor_execute", record)

        subscriptions = await reddit.list_for_guild(1)
        messages = await automation.list_auto_messages(1)
        self.assertEqual(len(subscriptions), 1)
        self.assertEqual(len(messages), 1)
        self.assertFalse(subscriptions[0].enabled)
        self.assertFalse(messages[0].enabled)
        self.assertEqual(subscriptions[0].last_seen_post_id, "new-post")
        self.assertEqual(ensure_utc(messages[0].last_sent), now)

    async def test_warn_concurrently_increments_exactly(self) -> None:
        async def warn(index: int) -> int:
            return await self.app.moderation.warn(
                ModerationRecord(1, index, 10, "member", "reason")
            )

        results = await asyncio.gather(*(warn(index) for index in range(12)))
        self.assertEqual(await self.app.moderation.warnings(1, 10), 12)
        self.assertEqual(sorted(results), list(range(1, 13)))
        async with self.app.database.session() as session:
            logs = await session.scalar(select(func.count()).select_from(ModerationLog))
        self.assertEqual(logs, 12)

    async def test_warning_transaction_rollback_keeps_count_and_log_consistent(self) -> None:
        def fail_log(_conn, _cursor, statement, _parameters, _context, _many) -> None:
            if statement.startswith("INSERT INTO moderation_logs"):
                raise RuntimeError("injected log failure")

        event.listen(self.app.database.engine.sync_engine, "before_cursor_execute", fail_log)
        try:
            with self.assertRaises(RuntimeError):
                await self.app.moderation.warn(ModerationRecord(1, 1, 10, "member", None))
        finally:
            event.remove(self.app.database.engine.sync_engine, "before_cursor_execute", fail_log)
        self.assertEqual(await self.app.moderation.warnings(1, 10), 0)

    async def test_automsg_concurrent_limit(self) -> None:
        for index in range(19):
            await self.app.automation.add_auto_message(
                guild_id=1,
                channel_id=index + 1,
                content="message",
                interval_minutes=5,
                use_embed=False,
            )

        results = await asyncio.gather(
            *(
                self.app.automation.add_auto_message(
                    guild_id=1,
                    channel_id=100 + index,
                    content="message",
                    interval_minutes=5,
                    use_embed=False,
                )
                for index in range(2)
            ),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(item, int) for item in results), 1)
        self.assertEqual(sum(isinstance(item, ConflictError) for item in results), 1)
        self.assertEqual(len(await self.app.automation_repo.list_auto_messages(1)), 20)

    async def test_reddit_concurrent_subscription_limit_and_duplicate(self) -> None:
        for index in range(19):
            await self.app.reddit.add(1, index + 1, f"sub{index:02}")
        results = await asyncio.gather(
            self.app.reddit.add(1, 100, "python"),
            self.app.reddit.add(1, 101, "learnpython"),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(item, int) for item in results), 1)
        self.assertEqual(len(await self.app.reddit_repo.list_for_guild(1)), 20)

        duplicates = await asyncio.gather(
            self.app.reddit.add(2, 100, "python"),
            self.app.reddit.add(2, 101, "python"),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(item, int) for item in duplicates), 1)
        self.assertEqual(sum(isinstance(item, ConflictError) for item in duplicates), 1)

    async def test_many_guild_limits_are_independent(self) -> None:
        ids = await asyncio.gather(
            *(self.app.reddit.add(guild, guild, "python") for guild in range(1, 11))
        )
        self.assertEqual(len(ids), 10)

    async def test_cross_guild_resource_access_is_rejected(self) -> None:
        await self.app.role_menus.create(
            message_id=100,
            guild_id=1,
            channel_id=10,
            role_ids=(5,),
            mode="toggle",
        )
        with self.assertRaises(PermissionDeniedError):
            await self.app.role_menus.get(100, 2)


class MigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_upgrade_from_previous_schema_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.db"
            database = Database(settings(f"sqlite+aiosqlite:///{path}"))
            async with database.engine.begin() as connection:
                await connection.execute(
                    text(
                        "CREATE TABLE reddit_subscriptions ("
                        "id INTEGER PRIMARY KEY, guild_id BIGINT NOT NULL, "
                        "channel_id BIGINT NOT NULL, subreddit VARCHAR(64) NOT NULL, "
                        "enabled BOOLEAN NOT NULL, last_seen_post_id VARCHAR(32), "
                        "created_at DATETIME NOT NULL)"
                    )
                )
                await connection.execute(
                    text(
                        "INSERT INTO reddit_subscriptions "
                        "(id, guild_id, channel_id, subreddit, enabled, created_at) "
                        "VALUES (1, 2, 3, 'python', 1, CURRENT_TIMESTAMP)"
                    )
                )
            await database.initialize_schema()
            await database.initialize_schema()
            async with database.engine.connect() as connection:
                versions = list(
                    await connection.scalars(
                        text("SELECT version FROM schema_migrations ORDER BY version")
                    )
                )
                images_only = await connection.scalar(
                    text("SELECT images_only FROM reddit_subscriptions WHERE id = 1")
                )
            self.assertEqual(versions, [1, 2])
            self.assertEqual(images_only, 0)
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
