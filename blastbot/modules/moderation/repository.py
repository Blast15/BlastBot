from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from blastbot.database.models import GuildConfig, ModerationLog, TempRole, UserState
from blastbot.database.session import Database


class ModerationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def add_log(
        self,
        *,
        guild_id: int,
        moderator_id: int,
        action: str,
        target_id: int,
        target_str: str | None,
        reason: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        async with self._database.session() as session, session.begin():
            session.add(
                ModerationLog(
                    guild_id=guild_id,
                    moderator_id=moderator_id,
                    action=action,
                    target_id=target_id,
                    target_str=target_str,
                    reason=reason,
                    extra_json=json.dumps(extra, ensure_ascii=False) if extra else None,
                )
            )

    async def add_warning_with_log(
        self,
        *,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        target_str: str | None,
        reason: str | None,
    ) -> int:
        async with self._database.session() as session, session.begin():
            row = await session.get(UserState, (guild_id, user_id))
            if row is None:
                row = UserState(guild_id=guild_id, user_id=user_id, warnings=1)
                session.add(row)
            else:
                row.warnings += 1
            await session.flush()
            session.add(
                ModerationLog(
                    guild_id=guild_id,
                    moderator_id=moderator_id,
                    action="WARN",
                    target_id=user_id,
                    target_str=target_str,
                    reason=reason,
                )
            )
            return row.warnings

    async def get_warnings(self, guild_id: int, user_id: int) -> int:
        async with self._database.session() as session:
            row = await session.get(UserState, (guild_id, user_id))
            return row.warnings if row else 0

    async def put_temp_role(
        self, *, guild_id: int, user_id: int, role_id: int, expires_at: datetime
    ) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(TempRole, (guild_id, user_id, role_id))
            if row is None:
                session.add(
                    TempRole(
                        guild_id=guild_id,
                        user_id=user_id,
                        role_id=role_id,
                        expires_at=expires_at,
                    )
                )
            else:
                row.expires_at = expires_at

    async def remove_temp_role(self, guild_id: int, user_id: int, role_id: int) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                delete(TempRole).where(
                    TempRole.guild_id == guild_id,
                    TempRole.user_id == user_id,
                    TempRole.role_id == role_id,
                )
            )

    async def expired_temp_roles(self, now: datetime) -> list[TempRole]:
        async with self._database.session() as session:
            result = await session.scalars(
                select(TempRole).where(TempRole.expires_at <= now)
            )
            return list(result)

    async def get_log_channel_id(self, guild_id: int) -> int | None:
        async with self._database.session() as session:
            config = await session.get(GuildConfig, guild_id)
            return config.log_channel_id if config else None
