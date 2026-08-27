from __future__ import annotations

import re

from sqlalchemy.exc import IntegrityError

from blastbot.core.errors import ConflictError, ResourceNotFoundError, ValidationError
from blastbot.modules.reddit.repository import RedditRepository

SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")


def normalize_subreddit(value: str) -> str:
    name = value.strip().removeprefix("https://www.reddit.com/").strip("/")
    if name.lower().startswith("r/"):
        name = name[2:]
    if not SUBREDDIT_RE.fullmatch(name):
        raise ValidationError(
            "invalid subreddit",
            "Tên cộng đồng không hợp lệ. Hãy nhập dạng `python`, `r/python` hoặc URL Reddit.",
        )
    return name.lower()


class RedditService:
    MAX_SUBSCRIPTIONS = 20

    def __init__(self, repository: RedditRepository) -> None:
        self.repository = repository

    async def add(self, guild_id: int, channel_id: int, subreddit: str) -> int:
        name = normalize_subreddit(subreddit)
        rows = await self.repository.list_for_guild(guild_id)
        if len(rows) >= self.MAX_SUBSCRIPTIONS:
            raise ConflictError(
                "reddit subscription limit reached",
                f"Server đã đạt giới hạn {self.MAX_SUBSCRIPTIONS} cộng đồng Reddit.",
            )
        if any(row.subreddit == name for row in rows):
            raise ConflictError(
                "subreddit already followed", f"Server đã theo dõi **r/{name}** rồi."
            )
        try:
            return await self.repository.create(guild_id, channel_id, name)
        except IntegrityError as exc:
            raise ConflictError(
                "subreddit already followed", f"Server đã theo dõi **r/{name}** rồi."
            ) from exc

    async def remove(self, guild_id: int, subscription_id: int) -> None:
        if not await self.repository.delete(guild_id, subscription_id):
            raise ResourceNotFoundError(
                "reddit subscription not found", "Không tìm thấy cấu hình Reddit này."
            )

    async def set_enabled(self, guild_id: int, subscription_id: int, enabled: bool) -> None:
        if not await self.repository.set_enabled(guild_id, subscription_id, enabled):
            raise ResourceNotFoundError(
                "reddit subscription not found", "Không tìm thấy cấu hình Reddit này."
            )
