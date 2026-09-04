from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import aiohttp
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from blastbot.core.config import Settings
from blastbot.core.errors import ExternalServiceError

logger = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"
SUBREDDIT_FROM_LINK = re.compile(r"/r/([^/]+)/", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class RedditPost:
    id: str
    subreddit: str
    title: str
    author: str
    permalink: str
    created_at: datetime
    text: str | None
    image_url: str | None
    flair: str | None


@dataclass(frozen=True, slots=True)
class RedditBatch:
    posts: list[RedditPost]
    cursor_found: bool
    ceiling_reached: bool


class RedditProtocolError(ExternalServiceError):
    """Reddit returned a response that does not match its documented protocol."""


def _http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    url = html.unescape(value)
    return url if len(url) <= 2048 and url.startswith(("https://", "http://")) else None


def _full_size_image(url: str) -> str:
    parts = urlsplit(url)
    if parts.hostname == "preview.redd.it":
        return urlunsplit((parts.scheme, "i.redd.it", parts.path, "", ""))
    return url


def extract_image(data: dict[str, Any]) -> str | None:
    direct = _http_url(data.get("url_overridden_by_dest"))
    if direct and direct.lower().split("?", 1)[0].endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".gif")
    ):
        return direct

    preview = data.get("preview")
    if isinstance(preview, dict):
        images = preview.get("images")
        if isinstance(images, list) and images:
            source = images[0].get("source") if isinstance(images[0], dict) else None
            if isinstance(source, dict):
                image = _http_url(source.get("url"))
                if image:
                    return _full_size_image(image)

    metadata = data.get("media_metadata")
    if isinstance(metadata, dict):
        for item in metadata.values():
            if not isinstance(item, dict):
                continue
            source = item.get("s")
            if isinstance(source, dict):
                image = _http_url(source.get("u") or source.get("gif"))
                if image:
                    return image

    thumbnail = _http_url(data.get("thumbnail"))
    return thumbnail


def parse_post(data: dict[str, Any]) -> RedditPost:
    post_id = data.get("id")
    title = data.get("title")
    subreddit = data.get("subreddit")
    if not all(isinstance(value, str) and value for value in (post_id, title, subreddit)):
        raise RedditProtocolError("Reddit post is missing id, title, or subreddit")
    if len(post_id) > 32 or len(title) > 300 or len(subreddit) > 64:
        raise RedditProtocolError("Reddit post contains an oversized required field")
    created = data.get("created_utc")
    try:
        created_at = datetime.fromtimestamp(float(created), tz=UTC)
    except (TypeError, ValueError, OSError) as exc:
        raise RedditProtocolError("Reddit post has an invalid created_utc") from exc
    permalink = data.get("permalink")
    url = (
        f"https://www.reddit.com{permalink}"
        if isinstance(permalink, str) and permalink.startswith("/")
        else f"https://www.reddit.com/comments/{post_id}"
    )
    text = data.get("selftext")
    if text is not None and not isinstance(text, str):
        raise RedditProtocolError("Reddit post has an invalid selftext")
    author = data.get("author")
    if author is not None and not isinstance(author, str):
        raise RedditProtocolError("Reddit post has an invalid author")
    flair = data.get("link_flair_text")
    if flair is not None and not isinstance(flair, str):
        raise RedditProtocolError("Reddit post has an invalid flair")
    return RedditPost(
        id=post_id,
        subreddit=subreddit,
        title=title,
        author=(author or "[deleted]")[:100],
        permalink=url,
        created_at=created_at,
        text=text.strip()[:4000] if isinstance(text, str) and text.strip() else None,
        image_url=extract_image(data),
        flair=flair[:100] if flair else None,
    )


class _FeedImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.images: list[str] = []
        self.originals: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag.lower() == "img":
            image = _http_url(attributes.get("src"))
            if image:
                self.images.append(image)
        elif tag.lower() == "a":
            target = _http_url(attributes.get("href"))
            if target and target.lower().split("?", 1)[0].endswith(
                (".jpg", ".jpeg", ".png", ".webp", ".gif")
            ):
                self.originals.append(target)


def _feed_image(content: str) -> str | None:
    parser = _FeedImageParser()
    parser.feed(content)
    if parser.originals:
        return _full_size_image(parser.originals[-1])
    preferred = [
        url
        for url in parser.images
        if any(host in url for host in ("preview.redd.it", "i.redd.it", "external-preview.redd.it"))
    ]
    candidates = preferred or parser.images
    return _full_size_image(candidates[-1]) if candidates else None


def _feed_datetime(value: str | None) -> datetime:
    if not value:
        raise RedditProtocolError("Reddit RSS entry is missing its timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise RedditProtocolError("Reddit RSS entry has an invalid timestamp") from exc


def parse_feed(xml: str, subreddit: str) -> list[RedditPost]:
    try:
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, DefusedXmlException) as exc:
        raise RedditProtocolError("Reddit returned an invalid RSS feed") from exc

    posts: list[RedditPost] = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = (entry.findtext(f"{ATOM}id") or "").strip()
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        link_node = entry.find(f"{ATOM}link")
        link = link_node.get("href") if link_node is not None else None
        if not raw_id or not title or not _http_url(link):
            raise RedditProtocolError("Reddit RSS entry is missing required fields")
        link_match = SUBREDDIT_FROM_LINK.search(link)
        post_subreddit = link_match.group(1).lower() if link_match else subreddit.lower()
        author = (entry.findtext(f"{ATOM}author/{ATOM}name") or "[deleted]").strip()
        author = author.removeprefix("/u/").removeprefix("u/")
        content = entry.findtext(f"{ATOM}content") or ""
        post_id = raw_id.removeprefix("t3_").rsplit("/", 1)[-1]
        if (
            len(post_id) > 32
            or len(title) > 300
            or len(post_subreddit) > 64
            or len(content) > 100_000
        ):
            raise RedditProtocolError("Reddit RSS entry contains an oversized field")
        posts.append(
            RedditPost(
                id=post_id,
                subreddit=post_subreddit,
                title=title,
                author=author[:100],
                permalink=link,
                created_at=_feed_datetime(
                    entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")
                ),
                text=None,
                image_url=_feed_image(content),
                flair=None,
            )
        )
    return posts


class RedditClient:
    OAUTH_PAGE_SIZE = 100
    MAX_CATCHUP_PAGES = 3

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)
        self._token_lock = asyncio.Lock()
        self._keyless_lock = asyncio.Lock()
        self._last_keyless_request = 0.0
        self._keyless_blocked_until = 0.0

    @property
    def has_oauth_credentials(self) -> bool:
        secret = self._settings.reddit_client_secret
        return bool(
            self._settings.reddit_client_id and secret is not None and secret.get_secret_value()
        )

    @property
    def mode(self) -> str:
        return "OAuth" if self.has_oauth_credentials else "RSS không key"

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self._settings.reddit_user_agent},
            )
        return self._session

    @staticmethod
    async def _json_object(response: aiohttp.ClientResponse, context: str) -> dict[str, Any]:
        try:
            payload = await response.json()
        except (aiohttp.ContentTypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RedditProtocolError(f"Reddit returned invalid JSON for {context}") from exc
        if not isinstance(payload, dict):
            raise RedditProtocolError(f"Reddit returned non-object JSON for {context}")
        return payload

    async def _access_token(self) -> str:
        client_id = self._settings.reddit_client_id
        secret = self._settings.reddit_client_secret
        if not client_id or secret is None or not secret.get_secret_value():
            raise RuntimeError("REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are required")
        if self._token and datetime.now(UTC) < self._token_expires_at:
            return self._token
        async with self._token_lock:
            if self._token and datetime.now(UTC) < self._token_expires_at:
                return self._token
            session = self._get_session()
            for attempt in range(2):
                async with session.post(
                    "https://www.reddit.com/api/v1/access_token",
                    headers={
                        "Authorization": aiohttp.encode_basic_auth(
                            client_id, secret.get_secret_value()
                        )
                    },
                    data={"grant_type": "client_credentials"},
                ) as response:
                    if (response.status == 429 or response.status >= 500) and attempt == 0:
                        delay = (
                            self._rate_limit_delay(response.headers)
                            if response.status == 429
                            else 2.0
                        )
                        logger.warning(
                            "Reddit token endpoint returned %d; retrying in %.0f seconds",
                            response.status,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    response.raise_for_status()
                    payload = await self._json_object(response, "OAuth token")
                    break
            else:  # pragma: no cover - both attempts always return or raise
                raise RuntimeError("Reddit OAuth token request failed")
            token = payload.get("access_token")
            if not isinstance(token, str) or not token:
                raise RedditProtocolError("Reddit did not return an access token")
            try:
                expires_in = max(60, int(payload.get("expires_in", 3600)) - 60)
            except (TypeError, ValueError) as exc:
                raise RedditProtocolError("Reddit returned an invalid token expiry") from exc
            self._token = token
            self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
            return token

    async def _oauth_page(
        self, subreddit: str, *, limit: int, after: str | None = None
    ) -> tuple[list[RedditPost], str | None]:
        session = self._get_session()
        url = f"https://oauth.reddit.com/r/{quote(subreddit, safe='+')}/new"
        for attempt in range(2):
            token = await self._access_token()
            async with session.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "limit": min(max(limit, 1), self.OAUTH_PAGE_SIZE),
                    "raw_json": 1,
                    **({"after": after} if after else {}),
                },
            ) as response:
                if response.status == 401 and attempt == 0:
                    self._token = None
                    continue
                if response.status == 429 or response.status >= 500:
                    delay = (
                        self._rate_limit_delay(response.headers) if response.status == 429 else 2.0
                    )
                    if attempt == 0:
                        logger.warning(
                            "Reddit OAuth returned %d; retrying in %.0f seconds",
                            response.status,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                response.raise_for_status()
                payload = await self._json_object(response, "OAuth listing")
                break
        else:  # pragma: no cover - both attempts always return or raise
            raise RuntimeError("Reddit OAuth request failed")
        listing = payload.get("data")
        if not isinstance(listing, dict) or not isinstance(listing.get("children"), list):
            raise RedditProtocolError("Reddit OAuth listing is missing data.children")
        next_after = listing.get("after")
        if next_after is not None and not isinstance(next_after, str):
            raise RedditProtocolError("Reddit OAuth listing has an invalid after cursor")
        children = listing["children"]
        posts: list[RedditPost] = []
        for child in children:
            if not isinstance(child, dict) or not isinstance(child.get("data"), dict):
                raise RedditProtocolError("Reddit OAuth listing contains an invalid child")
            posts.append(parse_post(child["data"]))
        return posts, next_after

    async def _newest_oauth(self, subreddit: str, limit: int) -> list[RedditPost]:
        posts, _ = await self._oauth_page(subreddit, limit=limit)
        return posts

    async def newest_since(
        self,
        subreddit: str,
        stop_ids: set[str],
        *,
        max_pages: int = MAX_CATCHUP_PAGES,
    ) -> RedditBatch:
        """Fetch newest-first posts through a bounded per-subreddit catch-up window."""
        if not self.has_oauth_credentials:
            posts = await self._newest_feed(subreddit, self.OAUTH_PAGE_SIZE)
            found = not stop_ids or stop_ids <= {post.id for post in posts}
            return RedditBatch(posts, found, bool(stop_ids and not found))

        posts: list[RedditPost] = []
        seen_ids: set[str] = set()
        after: str | None = None
        found_ids: set[str] = set()
        found = not stop_ids
        for _ in range(max_pages):
            page, after = await self._oauth_page(
                subreddit, limit=self.OAUTH_PAGE_SIZE, after=after
            )
            posts.extend(post for post in page if post.id not in seen_ids)
            seen_ids.update(post.id for post in page)
            found_ids.update(post.id for post in page if post.id in stop_ids)
            found = stop_ids <= found_ids
            if found or not after:
                break
        return RedditBatch(posts, found, bool(stop_ids and not found and after))

    @staticmethod
    def _rate_limit_delay(headers: aiohttp.typedefs.LooseHeaders) -> float:
        for name in ("Retry-After", "x-ratelimit-reset"):
            value = headers.get(name) if hasattr(headers, "get") else None
            try:
                if value is not None:
                    return min(max(float(value), 1.0), 120.0)
            except (TypeError, ValueError):
                continue
        return 60.0

    async def _newest_feed_path(
        self, path: str, fallback_subreddit: str, limit: int
    ) -> list[RedditPost]:
        if not self._settings.reddit_keyless_fallback:
            raise RuntimeError("Reddit OAuth credentials are missing and RSS fallback is disabled")
        async with self._keyless_lock:
            for attempt in range(2):
                now = time.monotonic()
                wait_for = max(
                    self._keyless_blocked_until - now,
                    7.0 - (now - self._last_keyless_request),
                    0.0,
                )
                if wait_for:
                    await asyncio.sleep(wait_for)
                session = self._get_session()
                url = f"https://www.reddit.com/r/{path}/new.rss"
                async with session.get(
                    url,
                    headers={"Accept": "application/atom+xml, application/xml;q=0.9"},
                    params={"limit": min(max(limit, 1), 100)},
                ) as response:
                    self._last_keyless_request = time.monotonic()
                    if response.status == 429:
                        delay = self._rate_limit_delay(response.headers) + 1.0
                        self._keyless_blocked_until = time.monotonic() + delay
                        if attempt == 0:
                            logger.warning(
                                "Reddit RSS rate limited; retrying in %.0f seconds",
                                delay,
                            )
                            continue
                        raise RuntimeError(
                            f"Reddit RSS rate limit persisted after retry ({delay:.0f}s)"
                        )
                    response.raise_for_status()
                    feed = await response.text()
                    remaining = response.headers.get("x-ratelimit-remaining")
                    try:
                        if remaining is not None and float(remaining) < 1.0:
                            self._keyless_blocked_until = time.monotonic() + self._rate_limit_delay(
                                response.headers
                            )
                    except ValueError:
                        logger.debug("Invalid Reddit rate-limit header: %r", remaining)
                    return parse_feed(feed, fallback_subreddit)
        return []

    async def _newest_feed(self, subreddit: str, limit: int) -> list[RedditPost]:
        return await self._newest_feed_path(quote(subreddit, safe=""), subreddit, limit)

    async def newest_many(
        self, subreddits: list[str], *, limit: int = 100
    ) -> dict[str, list[RedditPost]]:
        names = list(dict.fromkeys(name.lower() for name in subreddits))
        grouped = {name: [] for name in names}
        if not names:
            return grouped
        for name in names:
            grouped[name] = await self.newest(name, limit=limit)
        return grouped

    async def newest(self, subreddit: str, *, limit: int = 25) -> list[RedditPost]:
        if self.has_oauth_credentials:
            return await self._newest_oauth(subreddit, limit)
        return await self._newest_feed(subreddit, limit)
