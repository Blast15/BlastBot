from __future__ import annotations

from dataclasses import dataclass

from blastbot.modules.configuration.repository import GuildConfigRepository


@dataclass(frozen=True, slots=True)
class GuildConfigData:
    guild_id: int
    log_channel_id: int | None
    legacy_welcome_channel_id: int | None


class GuildConfigService:
    def __init__(self, repository: GuildConfigRepository) -> None:
        self.repository = repository

    async def get(self, guild_id: int) -> GuildConfigData:
        row = await self.repository.get(guild_id)
        return GuildConfigData(
            guild_id=guild_id,
            log_channel_id=row.log_channel_id if row else None,
            legacy_welcome_channel_id=row.welcome_channel_id if row else None,
        )

    async def set_log_channel(self, guild_id: int, channel_id: int | None) -> None:
        await self.repository.set_log_channel(guild_id, channel_id)
