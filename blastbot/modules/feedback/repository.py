from __future__ import annotations

from sqlalchemy import func, select

from blastbot.database.models import GuildConfig, SuggestionMessage, SuggestionVote
from blastbot.database.session import Database


class FeedbackRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def register_message(self, guild_id: int, message_id: int) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(SuggestionMessage, message_id)
            if row is None:
                session.add(SuggestionMessage(guild_id=guild_id, message_id=message_id))

    async def toggle_vote(
        self, message_id: int, user_id: int, vote: int
    ) -> tuple[int, int]:
        async with self._database.session() as session, session.begin():
            row = await session.get(SuggestionVote, (message_id, user_id))
            if row and row.vote == vote:
                await session.delete(row)
            elif row:
                row.vote = vote
            else:
                session.add(
                    SuggestionVote(message_id=message_id, user_id=user_id, vote=vote)
                )
            await session.flush()
            counts = await session.execute(
                select(SuggestionVote.vote, func.count())
                .where(SuggestionVote.message_id == message_id)
                .group_by(SuggestionVote.vote)
            )
            values = {int(v): int(count) for v, count in counts.all()}
            return values.get(1, 0), values.get(-1, 0)

    async def get_log_channel_id(self, guild_id: int) -> int | None:
        async with self._database.session() as session:
            row = await session.get(GuildConfig, guild_id)
            return row.log_channel_id if row else None
