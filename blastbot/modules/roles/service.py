from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar

from blastbot.core.errors import ResourceNotFoundError, ValidationError
from blastbot.database.models import RoleMenu
from blastbot.modules.roles.repository import RoleMenuRepository


@dataclass(frozen=True, slots=True)
class RoleMenuData:
    message_id: int
    guild_id: int
    channel_id: int
    role_ids: tuple[int, ...]
    mode: str


class RoleMenuService:
    MODES: ClassVar[set[str]] = {"toggle", "single"}

    def __init__(self, repository: RoleMenuRepository) -> None:
        self.repository = repository

    @staticmethod
    def _data(row: RoleMenu) -> RoleMenuData:
        try:
            role_ids = tuple(int(value) for value in json.loads(row.role_ids))
        except (TypeError, ValueError, json.JSONDecodeError):
            role_ids = ()
        return RoleMenuData(
            message_id=row.message_id,
            guild_id=row.guild_id,
            channel_id=row.channel_id,
            role_ids=role_ids,
            mode=row.mode,
        )

    async def create(
        self,
        *,
        message_id: int,
        guild_id: int,
        channel_id: int,
        role_ids: tuple[int, ...],
        mode: str,
    ) -> None:
        if mode not in self.MODES:
            raise ValidationError(
                "invalid role menu mode", "Mode role menu không hợp lệ."
            )
        unique = tuple(dict.fromkeys(role_ids))
        if not 1 <= len(unique) <= 25:
            raise ValidationError(
                "invalid role count", "Role menu cần từ 1 đến 25 role."
            )
        await self.repository.save(
            message_id=message_id,
            guild_id=guild_id,
            channel_id=channel_id,
            role_ids=unique,
            mode=mode,
        )

    async def get(self, message_id: int) -> RoleMenuData:
        row = await self.repository.get(message_id)
        if row is None:
            raise ResourceNotFoundError(
                "role menu not found", "Role menu không còn tồn tại."
            )
        return self._data(row)

    async def list_for_guild(self, guild_id: int) -> list[RoleMenuData]:
        return [
            self._data(row) for row in await self.repository.list_for_guild(guild_id)
        ]
