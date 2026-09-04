from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
import discord
from sqlalchemy.exc import SQLAlchemyError

from blastbot.core.config import Settings
from blastbot.modules.reddit.client import (
    RedditBatch,
    RedditClient,
    RedditPost,
    RedditProtocolError,
)
from blastbot.modules.reddit.cog import RedditCog


def make_settings(*, oauth: bool = True) -> Settings:
    return Settings(
        DISCORD_TOKEN="x" * 40,
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        OWNER_ID="",
        DEV_GUILD_ID="",
        REDDIT_CLIENT_ID="client" if oauth else "",
        REDDIT_CLIENT_SECRET="secret" if oauth else "",
        REDDIT_KEYLESS_FALLBACK=not oauth,
    )


def post(post_id: str, subreddit: str = "python", *, image: bool = True) -> RedditPost:
    return RedditPost(
        id=post_id,
        subreddit=subreddit,
        title=f"Post {post_id}",
        author="author",
        permalink=f"https://reddit.com/comments/{post_id}",
        created_at=datetime.now(UTC),
        text=None,
        image_url="https://i.redd.it/image.jpg" if image else None,
        flair=None,
    )


def discord_error() -> discord.HTTPException:
    return discord.HTTPException(
        SimpleNamespace(status=500, reason="test", headers={}), "injected"
    )


class FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        payload: object | None = None,
        json_error: BaseException | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.reason = "test"
        self.headers = headers or {}
        self._payload = payload
        self._json_error = json_error

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def json(self) -> object:
        if self._json_error:
            raise self._json_error
        return self._payload

    async def text(self) -> str:
        return str(self._payload or "")

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                SimpleNamespace(real_url="https://reddit.test"),
                (),
                status=self.status,
                message=self.reason,
                headers=self.headers,
            )


class FakeSession:
    def __init__(
        self,
        *,
        posts: list[FakeResponse] | None = None,
        gets: list[FakeResponse] | None = None,
    ) -> None:
        self.posts = posts or []
        self.gets = gets or []
        self.post_calls = 0
        self.get_calls = 0

    def post(self, *_args: object, **_kwargs: object) -> FakeResponse:
        response = self.posts[self.post_calls]
        self.post_calls += 1
        return response

    def get(self, *_args: object, **_kwargs: object) -> FakeResponse:
        response = self.gets[self.get_calls]
        self.get_calls += 1
        return response


class RedditClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_json_and_non_object_are_protocol_errors(self) -> None:
        for response in (
            FakeResponse(json_error=json.JSONDecodeError("bad", "x", 0)),
            FakeResponse(payload=[]),
        ):
            client = RedditClient(make_settings())
            client._get_session = (  # type: ignore[method-assign]
                lambda response=response: FakeSession(posts=[response])
            )
            with self.assertRaises(RedditProtocolError):
                await client._access_token()

    async def test_missing_token_is_protocol_error(self) -> None:
        client = RedditClient(make_settings())
        client._get_session = lambda: FakeSession(posts=[FakeResponse(payload={})])  # type: ignore[method-assign]
        with self.assertRaises(RedditProtocolError):
            await client._access_token()

    async def test_token_5xx_retries(self) -> None:
        client = RedditClient(make_settings())
        session = FakeSession(
            posts=[
                FakeResponse(status=500),
                FakeResponse(payload={"access_token": "token", "expires_in": 3600}),
            ]
        )
        client._get_session = lambda: session  # type: ignore[method-assign]
        with patch("blastbot.modules.reddit.client.asyncio.sleep", new=AsyncMock()):
            self.assertEqual(await client._access_token(), "token")
        self.assertEqual(session.post_calls, 2)

    async def test_malformed_oauth_listing_is_protocol_error(self) -> None:
        client = RedditClient(make_settings())
        client._access_token = AsyncMock(return_value="token")  # type: ignore[method-assign]
        client._get_session = lambda: FakeSession(gets=[FakeResponse(payload={})])  # type: ignore[method-assign]
        with self.assertRaises(RedditProtocolError):
            await client._oauth_page("python", limit=100)

    async def test_reddit_oauth_401_refresh(self) -> None:
        client = RedditClient(make_settings())
        client._token = "old"
        client._access_token = AsyncMock(side_effect=["old", "new"])  # type: ignore[method-assign]
        session = FakeSession(
            gets=[
                FakeResponse(status=401),
                FakeResponse(payload={"data": {"children": [], "after": None}}),
            ]
        )
        client._get_session = lambda: session  # type: ignore[method-assign]
        posts, after = await client._oauth_page("python", limit=100)
        self.assertEqual((posts, after), ([], None))
        self.assertIsNone(client._token)
        self.assertEqual(session.get_calls, 2)

    async def test_reddit_429_and_5xx_retry_paths(self) -> None:
        for status in (429, 500):
            client = RedditClient(make_settings())
            client._access_token = AsyncMock(return_value="token")  # type: ignore[method-assign]
            session = FakeSession(
                gets=[
                    FakeResponse(status=status, headers={"Retry-After": "1"}),
                    FakeResponse(payload={"data": {"children": [], "after": None}}),
                ]
            )
            client._get_session = lambda session=session: session  # type: ignore[method-assign]
            with patch("blastbot.modules.reddit.client.asyncio.sleep", new=AsyncMock()):
                self.assertEqual(await client._oauth_page("python", limit=100), ([], None))
            self.assertEqual(session.get_calls, 2)

    async def test_reddit_pagination_over_100_posts(self) -> None:
        client = RedditClient(make_settings())
        page_one = [post(str(index)) for index in range(250, 150, -1)]
        page_two = [post(str(index)) for index in range(150, 50, -1)]
        page_three = [post(str(index)) for index in range(50, 0, -1)]
        client._oauth_page = AsyncMock(  # type: ignore[method-assign]
            side_effect=[
                (page_one, "next"),
                (page_two, "last"),
                (page_three, None),
            ]
        )
        batch = await client.newest_since("python", {"225", "25"})
        self.assertEqual(len(batch.posts), 250)
        self.assertTrue(batch.cursor_found)
        self.assertEqual(client._oauth_page.await_count, 3)

    async def test_cursor_missing_hits_bounded_ceiling(self) -> None:
        client = RedditClient(make_settings())
        client._oauth_page = AsyncMock(  # type: ignore[method-assign]
            side_effect=[([post(str(page_index))], f"next-{page_index}") for page_index in range(3)]
        )
        batch = await client.newest_since("python", {"missing"})
        self.assertFalse(batch.cursor_found)
        self.assertTrue(batch.ceiling_reached)
        self.assertEqual(client._oauth_page.await_count, 3)


class RedditPollTests(unittest.IsolatedAsyncioTestCase):
    def make_cog(
        self, *, rows: list[SimpleNamespace], client: object, channel: object
    ) -> RedditCog:
        repository = SimpleNamespace(
            list_enabled=AsyncMock(return_value=rows),
            mark_seen=AsyncMock(),
            set_enabled=AsyncMock(),
        )
        cog = object.__new__(RedditCog)
        cog.client = client
        cog.bot = SimpleNamespace(
            app=SimpleNamespace(reddit_repo=repository),
            get_guild=lambda _guild_id: SimpleNamespace(
                get_channel=lambda _channel_id: channel
            ),
        )
        return cog

    async def test_reddit_malformed_json_does_not_kill_polling(self) -> None:
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=10,
            subreddit="python",
            last_seen_post_id="old",
            images_only=False,
        )
        client = SimpleNamespace(
            newest_since=AsyncMock(
                side_effect=[
                    RedditProtocolError("bad payload"),
                    RedditBatch([post("new"), post("old")], True, False),
                ]
            )
        )
        channel = SimpleNamespace(send=AsyncMock())
        cog = self.make_cog(rows=[row], client=client, channel=channel)
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._poll_once()
            await cog._poll_once()
        channel.send.assert_awaited_once()

    async def test_reddit_busy_subreddit_does_not_starve_others(self) -> None:
        rows = [
            SimpleNamespace(
                id=index,
                guild_id=1,
                channel_id=10,
                subreddit=name,
                last_seen_post_id="old",
                images_only=False,
            )
            for index, name in enumerate(("busy", "quiet"), start=1)
        ]
        client = SimpleNamespace(
            newest_since=AsyncMock(
                side_effect=[
                    aiohttp.ClientConnectionError("down"),
                    RedditBatch([post("new", "quiet"), post("old", "quiet")], True, False),
                ]
            )
        )
        channel = SimpleNamespace(send=AsyncMock())
        cog = self.make_cog(rows=rows, client=client, channel=channel)
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._poll_once()
        channel.send.assert_awaited_once()
        self.assertEqual(client.newest_since.await_count, 2)

    async def test_reddit_runtime_error_does_not_stop_next_iteration(self) -> None:
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=10,
            subreddit="python",
            last_seen_post_id="old",
            images_only=False,
        )
        client = SimpleNamespace(
            newest_since=AsyncMock(
                side_effect=[
                    RuntimeError("protocol failure"),
                    RedditBatch([post("new"), post("old")], True, False),
                ]
            )
        )
        channel = SimpleNamespace(send=AsyncMock())
        cog = self.make_cog(rows=[row], client=client, channel=channel)
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._poll_once()
            await cog._poll_once()
        channel.send.assert_awaited_once()

    async def test_reddit_images_only_advances_cursor(self) -> None:
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=10,
            subreddit="python",
            last_seen_post_id="old",
            images_only=True,
        )
        channel = SimpleNamespace(send=AsyncMock())
        cog = self.make_cog(rows=[row], client=SimpleNamespace(), channel=channel)
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._deliver(row, [post("new", image=False), post("old")])
        channel.send.assert_not_awaited()
        cog.bot.app.reddit_repo.mark_seen.assert_awaited_once_with(1, "new")

    async def test_reddit_delivers_over_100_posts_in_chronological_order(self) -> None:
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=10,
            subreddit="python",
            last_seen_post_id="old",
            images_only=False,
        )
        channel = SimpleNamespace(send=AsyncMock())
        cog = self.make_cog(rows=[row], client=SimpleNamespace(), channel=channel)
        posts = [post(str(index)) for index in range(120, 0, -1)] + [post("old")]
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._deliver(row, posts)
        self.assertEqual(channel.send.await_count, 120)
        calls = cog.bot.app.reddit_repo.mark_seen.await_args_list
        self.assertEqual(calls[0].args, (1, "1"))
        self.assertEqual(calls[-1].args, (1, "120"))

    async def test_reddit_partial_send_restart_behavior_is_at_least_once(self) -> None:
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=10,
            subreddit="python",
            last_seen_post_id="old",
            images_only=False,
        )
        channel = SimpleNamespace(send=AsyncMock())
        cog = self.make_cog(rows=[row], client=SimpleNamespace(), channel=channel)
        cog.bot.app.reddit_repo.mark_seen.side_effect = [SQLAlchemyError("db"), None]
        batch = [post("new"), post("old")]
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            with self.assertRaises(SQLAlchemyError):
                await cog._deliver(row, batch)
            await cog._deliver(row, batch)
        self.assertEqual(channel.send.await_count, 2)

    async def test_reddit_send_failure_resumes_after_last_persisted_post(self) -> None:
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=10,
            subreddit="python",
            last_seen_post_id="old",
            images_only=False,
        )
        channel = SimpleNamespace(send=AsyncMock(side_effect=[None, discord_error()]))
        cog = self.make_cog(rows=[row], client=SimpleNamespace(), channel=channel)
        batch = [post("new-2"), post("new-1"), post("old")]
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._deliver(row, batch)
        cog.bot.app.reddit_repo.mark_seen.assert_awaited_once_with(1, "new-1")
        row.last_seen_post_id = "new-1"
        channel.send = AsyncMock()
        cog.bot.app.reddit_repo.mark_seen.reset_mock()
        with patch("blastbot.modules.reddit.cog.discord.TextChannel", object):
            await cog._deliver(row, batch)
        channel.send.assert_awaited_once()
        cog.bot.app.reddit_repo.mark_seen.assert_awaited_once_with(1, "new-2")


if __name__ == "__main__":
    unittest.main()
