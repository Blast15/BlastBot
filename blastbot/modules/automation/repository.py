from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select

from blastbot.database.models import AutoMessage, Greeting
from blastbot.database.session import Database
from blastbot.shared.time import ensure_utc


class AutomationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_greeting(self, guild_id: int, kind: str) -> Greeting | None:
        async with self._database.session() as session:
            return await session.get(Greeting, (guild_id, kind))

    async def configure_greeting(
        self,
        *,
        guild_id: int,
        kind: str,
        channel_id: int,
        use_embed: bool,
        title: str | None,
        message: str,
        color: int | None,
    ) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(Greeting, (guild_id, kind))
            if row is None:
                row = Greeting(guild_id=guild_id, kind=kind)
                session.add(row)
            row.enabled = True
            row.channel_id = channel_id
            row.use_embed = use_embed
            row.title = title
            row.message = message
            row.color = color

    async def set_greeting_enabled(self, guild_id: int, kind: str, enabled: bool) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(Greeting, (guild_id, kind))
            if row is None:
                session.add(Greeting(guild_id=guild_id, kind=kind, enabled=enabled))
            else:
                row.enabled = enabled

    async def create_auto_message(
        self,
        *,
        guild_id: int,
        channel_id: int,
        content: str,
        interval_minutes: int,
        use_embed: bool,
    ) -> int:
        async with self._database.session() as session, session.begin():
            row = AutoMessage(
                guild_id=guild_id,
                channel_id=channel_id,
                content=content,
                interval_minutes=interval_minutes,
                use_embed=use_embed,
            )
            session.add(row)
            await session.flush()
            return row.id

    async def list_auto_messages(self, guild_id: int) -> list[AutoMessage]:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(AutoMessage).where(AutoMessage.guild_id == guild_id).order_by(AutoMessage.id)
            )
            return list(rows)

    async def delete_auto_message(self, guild_id: int, auto_id: int) -> bool:
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                delete(AutoMessage).where(
                    AutoMessage.id == auto_id, AutoMessage.guild_id == guild_id
                )
            )
            return bool(result.rowcount)

    async def toggle_auto_message(self, guild_id: int, auto_id: int, enabled: bool) -> bool:
        async with self._database.session() as session, session.begin():
            row = await session.get(AutoMessage, auto_id)
            if row is None or row.guild_id != guild_id:
                return False
            row.enabled = enabled
            return True

    async def due_auto_messages(self, now: datetime) -> list[AutoMessage]:
        async with self._database.session() as session:
            rows = await session.scalars(select(AutoMessage).where(AutoMessage.enabled.is_(True)))
            return [
                row
                for row in rows
                if row.last_sent is None
                or ensure_utc(row.last_sent) + timedelta(minutes=row.interval_minutes) <= ensure_utc(now)
            ]

    async def mark_sent(self, auto_id: int, now: datetime) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(AutoMessage, auto_id)
            if row:
                row.last_sent = now
