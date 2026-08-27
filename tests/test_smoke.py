from __future__ import annotations

import unittest

from defusedxml.common import DefusedXmlException

from blastbot.core.bot import BlastBot
from blastbot.core.config import Settings
from blastbot.core.context import build_context
from blastbot.core.extensions import enabled_extensions
from blastbot.modules.help.cog import category_embed
from blastbot.modules.moderation.service import ModerationRecord
from blastbot.modules.reddit.client import parse_feed


class BlastBotSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.settings = Settings(
            DISCORD_TOKEN="x" * 40,
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            OWNER_ID="",
            DEV_GUILD_ID="",
            REDDIT_CLIENT_ID="",
            REDDIT_CLIENT_SECRET="",
            REDDIT_KEYLESS_FALLBACK=False,
        )
        self.app = await build_context(self.settings)

    async def asyncTearDown(self) -> None:
        await self.app.database.dispose()

    async def test_service_round_trip(self) -> None:
        await self.app.guild_config.set_log_channel(1, 101)
        self.assertEqual((await self.app.guild_config.get(1)).log_channel_id, 101)

        record = ModerationRecord(1, 10, 20, "member", "reason")
        self.assertEqual(await self.app.moderation.warn(record), 1)
        self.assertEqual(await self.app.moderation.warnings(1, 20), 1)

        await self.app.feedback.register_suggestion(1, 1001)
        self.assertEqual(await self.app.feedback.vote(1001, 20, 1), (1, 0))

        auto_id = await self.app.automation.add_auto_message(
            guild_id=1,
            channel_id=101,
            content="Ping",
            interval_minutes=5,
            use_embed=True,
        )
        await self.app.automation.set_auto_message_enabled(1, auto_id, False)
        self.assertFalse(
            (await self.app.automation_repo.list_auto_messages(1))[0].enabled
        )

        await self.app.role_menus.create(
            message_id=2001,
            guild_id=1,
            channel_id=101,
            role_ids=(30, 31),
            mode="single",
        )
        self.assertEqual((await self.app.role_menus.get(2001)).role_ids, (30, 31))

        panel_id = await self.app.tickets.create_panel(
            guild_id=1,
            category_id=3001,
            title="Support",
            content="Open a ticket",
            button_label="Open",
            mention_role_id=30,
        )
        reservation = await self.app.tickets.reserve(1, 20, panel_id)
        await self.app.tickets.finalize(reservation.id, 4001)
        self.assertEqual(
            (await self.app.tickets.get_panel(panel_id, 1)).title, "Support"
        )

        reddit_id = await self.app.reddit.add(1, 101, "r/python")
        await self.app.reddit_repo.mark_seen(reddit_id, "abc")
        rows = await self.app.reddit_repo.list_for_guild(1)
        self.assertEqual(rows[0].last_seen_post_id, "abc")

    async def test_extensions_and_help(self) -> None:
        bot = BlastBot(self.app)
        loaded: list[str] = []
        try:
            for extension in enabled_extensions(self.settings):
                await bot.load_extension(extension)
                loaded.append(extension)
            help_cog = bot.get_cog("HelpCog")
            self.assertEqual(type(help_cog).__name__, "HelpCog")
            self.assertIsNotNone(help_cog)
            commands_ = help_cog._commands()
            names = {command.qualified_name for command in commands_}
            self.assertIn("ticket add", names)
            self.assertIn("ticket-config limit", names)
            self.assertNotIn("add", names)
            for name, items in help_cog._categories().items():
                self.assertLessEqual(len(category_embed(name, items)), 6000)
        finally:
            for extension in reversed(loaded):
                await bot.unload_extension(extension)

    def test_reddit_feed_parser_rejects_entities(self) -> None:
        malicious = """<?xml version="1.0"?><!DOCTYPE feed [<!ENTITY xxe "blocked">]><feed xmlns="http://www.w3.org/2005/Atom"><title>&xxe;</title></feed>"""
        with self.assertRaises(DefusedXmlException):
            parse_feed(malicious, "python")


if __name__ == "__main__":
    unittest.main()
