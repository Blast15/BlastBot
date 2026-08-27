from __future__ import annotations

from blastbot.database.models import GuildConfig
from blastbot.database.session import Database


class GuildConfigRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get(self, guild_id: int) -> GuildConfig | None:
        async with self._database.session() as session:
            return await session.get(GuildConfig, guild_id)

    async def set_log_channel(self, guild_id: int, channel_id: int | None) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(GuildConfig, guild_id)
            if row is None:
                row = GuildConfig(guild_id=guild_id)
                session.add(row)
            row.log_channel_id = channel_id
