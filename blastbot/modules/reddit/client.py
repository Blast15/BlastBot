from __future__ import annotations

import asyncio
import html
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp

from blastbot.core.config import Settings

logger = logging.getLogger(__name__)


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


def _http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    url = html.unescape(value)
    return url if url.startswith(("https://", "http://")) else None


def extract_image(data: dict[str, Any]) -> str | None:
    direct = _http_url(data.get("url_overridden_by_dest"))
    if direct and direct.lower().split("?", 1)[0].endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return direct

    preview = data.get("preview")
    if isinstance(preview, dict):
        images = preview.get("images")
        if isinstance(images, list) and images:
            source = images[0].get("source") if isinstance(images[0], dict) else None
            if isinstance(source, dict):
                image = _http_url(source.get("url"))
                if image:
                    return image

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


def parse_post(data: dict[str, Any]) -> RedditPost | None:
    post_id = data.get("id")
    title = data.get("title")
    subreddit = data.get("subreddit")
    if not all(isinstance(value, str) and value for value in (post_id, title, subreddit)):
        return None
    created = data.get("created_utc")
    try:
        created_at = datetime.fromtimestamp(float(created), tz=UTC)
    except (TypeError, ValueError, OSError):
        created_at = datetime.now(UTC)
    permalink = data.get("permalink")
    url = (
        f"https://www.reddit.com{permalink}"
        if isinstance(permalink, str) and permalink.startswith("/")
        else f"https://www.reddit.com/comments/{post_id}"
    )
    text = data.get("selftext")
    return RedditPost(
        id=post_id,
        subreddit=subreddit,
        title=title,
        author=str(data.get("author") or "[deleted]"),
        permalink=url,
        created_at=created_at,
        text=text.strip() if isinstance(text, str) and text.strip() else None,
        image_url=extract_image(data),
        flair=str(data["link_flair_text"]) if data.get("link_flair_text") else None,
    )


class RedditClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)
        self._token_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(
                timeout=timeout, headers={"User-Agent": self._settings.reddit_user_agent}
            )
        return self._session

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
            async with session.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=aiohttp.BasicAuth(client_id, secret.get_secret_value()),
                data={"grant_type": "client_credentials"},
            ) as response:
                response.raise_for_status()
                payload = await response.json()
            token = payload.get("access_token")
            if not isinstance(token, str):
                raise RuntimeError("Reddit did not return an access token")
            expires_in = max(60, int(payload.get("expires_in", 3600)) - 60)
            self._token = token
            self._token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
            return token

    async def newest(self, subreddit: str, *, limit: int = 25) -> list[RedditPost]:
        token = await self._access_token()
        session = self._get_session()
        url = f"https://oauth.reddit.com/r/{quote(subreddit, safe='')}/new"
        async with session.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": min(max(limit, 1), 100), "raw_json": 1},
        ) as response:
            if response.status == 429:
                retry_after = response.headers.get("Retry-After", "unknown")
                raise RuntimeError(f"Reddit rate limit reached; retry after {retry_after}s")
            response.raise_for_status()
            payload = await response.json()
        children = payload.get("data", {}).get("children", [])
        posts: list[RedditPost] = []
        for child in children:
            if not isinstance(child, dict) or not isinstance(child.get("data"), dict):
                continue
            post = parse_post(child["data"])
            if post is not None:
                posts.append(post)
        return posts
