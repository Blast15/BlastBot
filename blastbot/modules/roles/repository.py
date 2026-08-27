from __future__ import annotations

import json

from sqlalchemy import delete, select

from blastbot.database.models import RoleMenu
from blastbot.database.session import Database


class RoleMenuRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def save(
        self,
        *,
        message_id: int,
        guild_id: int,
        channel_id: int,
        role_ids: tuple[int, ...],
        mode: str,
    ) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(RoleMenu, message_id)
            if row is None:
                session.add(
                    RoleMenu(
                        message_id=message_id,
                        guild_id=guild_id,
                        channel_id=channel_id,
                        role_ids=json.dumps(role_ids),
                        mode=mode,
                    )
                )
            else:
                row.guild_id = guild_id
                row.channel_id = channel_id
                row.role_ids = json.dumps(role_ids)
                row.mode = mode

    async def get(self, message_id: int) -> RoleMenu | None:
        async with self._database.session() as session:
            return await session.get(RoleMenu, message_id)

    async def list_for_guild(self, guild_id: int) -> list[RoleMenu]:
        async with self._database.session() as session:
            return list(
                await session.scalars(
                    select(RoleMenu)
                    .where(RoleMenu.guild_id == guild_id)
                    .order_by(RoleMenu.message_id.desc())
                )
            )

    async def delete(self, guild_id: int, message_id: int) -> bool:
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                delete(RoleMenu).where(
                    RoleMenu.guild_id == guild_id,
                    RoleMenu.message_id == message_id,
                )
            )
            return bool(result.rowcount)
