from __future__ import annotations

from sqlalchemy import delete, select

from blastbot.database.models import RedditSubscription
from blastbot.database.session import Database


class RedditRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(
        self,
        guild_id: int,
        channel_id: int,
        subreddit: str,
        images_only: bool = False,
    ) -> int:
        async with self._database.session() as session, session.begin():
            row = RedditSubscription(
                guild_id=guild_id,
                channel_id=channel_id,
                subreddit=subreddit,
                images_only=images_only,
            )
            session.add(row)
            await session.flush()
            return row.id

    async def list_for_guild(self, guild_id: int) -> list[RedditSubscription]:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(RedditSubscription)
                .where(RedditSubscription.guild_id == guild_id)
                .order_by(RedditSubscription.id)
            )
            return list(rows)

    async def list_enabled(self) -> list[RedditSubscription]:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(RedditSubscription).where(RedditSubscription.enabled.is_(True))
            )
            return list(rows)

    async def delete(self, guild_id: int, subscription_id: int) -> bool:
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                delete(RedditSubscription).where(
                    RedditSubscription.id == subscription_id,
                    RedditSubscription.guild_id == guild_id,
                )
            )
            return bool(result.rowcount)

    async def set_enabled(self, guild_id: int, subscription_id: int, enabled: bool) -> bool:
        async with self._database.session() as session, session.begin():
            row = await session.get(RedditSubscription, subscription_id)
            if row is None or row.guild_id != guild_id:
                return False
            row.enabled = enabled
            return True

    async def mark_seen(self, subscription_id: int, post_id: str) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(RedditSubscription, subscription_id)
            if row is not None:
                row.last_seen_post_id = post_id
