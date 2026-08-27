from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from defusedxml.common import DefusedXmlException

from blastbot.core.bot import BlastBot
from blastbot.core.config import Settings
from blastbot.core.context import build_context
from blastbot.core.extensions import enabled_extensions
from blastbot.modules.help.cog import category_embed
from blastbot.modules.moderation.service import ModerationRecord
from blastbot.modules.reddit.client import RedditClient, RedditPost, parse_feed
from blastbot.modules.reddit.cog import RedditCog, reddit_embed


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

        auto_id = await self.app.automation.add_auto_message(
            guild_id=1,
            channel_id=101,
            content="Ping",
            interval_minutes=5,
            use_embed=True,
        )
        await self.app.automation.set_auto_message_enabled(1, auto_id, False)
        self.assertFalse((await self.app.automation_repo.list_auto_messages(1))[0].enabled)

        await self.app.role_menus.create(
            message_id=2001,
            guild_id=1,
            channel_id=101,
            role_ids=(30, 31),
            mode="single",
        )
        self.assertEqual((await self.app.role_menus.get(2001)).role_ids, (30, 31))

        reddit_id = await self.app.reddit.add(1, 101, "r/python", images_only=True)
        await self.app.reddit_repo.mark_seen(reddit_id, "abc")
        rows = await self.app.reddit_repo.list_for_guild(1)
        self.assertEqual(rows[0].last_seen_post_id, "abc")
        self.assertTrue(rows[0].images_only)

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
            self.assertIn("reddit add", names)
            self.assertIn("warn", names)
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

    def test_reddit_embed_and_feed_prefer_full_image(self) -> None:
        feed = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><author><name>/u/test</name></author><content type="html">&lt;a href="https://i.redd.it/original.jpg"&gt;&lt;img src="https://preview.redd.it/thumb.jpg?width=320" /&gt;&lt;/a&gt;</content><id>t3_abc</id><link href="https://www.reddit.com/r/python/comments/abc/post/"/><published>2026-08-27T12:00:00Z</published><title>A long post title</title></entry></feed>"""  # noqa: E501
        self.assertEqual(parse_feed(feed, "python")[0].image_url, "https://i.redd.it/original.jpg")
        preview_only = feed.replace('&lt;a href="https://i.redd.it/original.jpg"&gt;', "").replace(
            "&lt;/a&gt;", ""
        )
        self.assertEqual(
            parse_feed(preview_only, "python")[0].image_url,
            "https://i.redd.it/thumb.jpg",
        )

        post = RedditPost(
            id="abc",
            subreddit="python",
            title="A **long** post title",
            author="test",
            permalink="https://www.reddit.com/comments/abc",
            created_at=datetime.now(UTC),
            text=None,
            image_url="https://i.redd.it/original.jpg",
            flair=None,
        )
        card = reddit_embed(post)
        self.assertIsNone(card.title)
        self.assertEqual(card.description, "**A \\*\\*long\\*\\* post title**")
        self.assertEqual(card.image.url, post.image_url)

    async def test_reddit_images_only_skips_post_and_marks_it_seen(self) -> None:
        channel = SimpleNamespace(send=AsyncMock())
        repository = SimpleNamespace(mark_seen=AsyncMock(), set_enabled=AsyncMock())
        cog = object.__new__(RedditCog)
        cog.bot = SimpleNamespace(
            app=SimpleNamespace(reddit_repo=repository),
            get_guild=lambda _guild_id: SimpleNamespace(get_channel=lambda _channel_id: channel),
        )
        post = RedditPost(
            id="without-image",
            subreddit="python",
            title="Text post",
            author="test",
            permalink="https://www.reddit.com/comments/without-image",
            created_at=datetime.now(UTC),
            text="content",
            image_url=None,
            flair=None,
        )
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=101,
            images_only=True,
            last_seen_post_id="previous",
        )

        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._deliver(row, [post])

        channel.send.assert_not_awaited()
        repository.mark_seen.assert_awaited_once_with(1, "without-image")

    async def test_reddit_oauth_poll_groups_subreddits_into_one_request(self) -> None:
        client = RedditClient(self.settings)
        client._newest_oauth = AsyncMock(return_value=[])
        with patch.object(
            RedditClient,
            "has_oauth_credentials",
            new_callable=lambda: property(lambda _: True),
        ):
            result = await client.newest_many(["python", "learnpython", "python"])
        self.assertEqual(result, {"python": [], "learnpython": []})
        client._newest_oauth.assert_awaited_once_with("python+learnpython", 100)


if __name__ == "__main__":
    unittest.main()
