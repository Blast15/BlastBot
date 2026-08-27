from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from blastbot.core.errors import TicketLimitReachedError
from blastbot.database.models import (
    Ticket,
    TicketBlacklist,
    TicketMember,
    TicketPanel,
    TicketSettings,
    TicketStaff,
    TicketTag,
)
from blastbot.database.session import Database
from blastbot.shared.time import ensure_utc


class TicketRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_settings(self, guild_id: int) -> TicketSettings:
        async with self._database.session() as session, session.begin():
            row = await session.get(TicketSettings, guild_id)
            if row is None:
                row = TicketSettings(guild_id=guild_id)
                session.add(row)
                await session.flush()
            return row

    async def update_settings(self, guild_id: int, **values: int | str | None) -> None:
        allowed = {
            "transcript_channel_id",
            "ticket_limit",
            "welcome_message",
            "claim_mode",
            "autoclose_hours",
        }
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return
        async with self._database.session() as session, session.begin():
            row = await session.get(TicketSettings, guild_id)
            if row is None:
                row = TicketSettings(guild_id=guild_id)
                session.add(row)
            for key, value in updates.items():
                setattr(row, key, value)

    async def reserve_ticket(
        self, *, guild_id: int, owner_id: int, panel_id: int | None
    ) -> Ticket:
        """Reserve a ticket slot and number atomically before Discord channel creation.

        The first write is an idempotent settings upsert, followed by an atomic
        counter increment with ``RETURNING``. PostgreSQL serializes the row update;
        SQLite serializes writers. If the per-user limit check fails, the transaction
        rolls back the counter increment as well.
        """
        async with self._database.session() as session, session.begin():
            dialect_name = session.get_bind().dialect.name
            if dialect_name == "sqlite":
                ensure_settings = sqlite_insert(TicketSettings).values(guild_id=guild_id)
                ensure_settings = ensure_settings.on_conflict_do_nothing(
                    index_elements=[TicketSettings.guild_id]
                )
            elif dialect_name == "postgresql":
                ensure_settings = postgresql_insert(TicketSettings).values(guild_id=guild_id)
                ensure_settings = ensure_settings.on_conflict_do_nothing(
                    index_elements=[TicketSettings.guild_id]
                )
            else:
                raise RuntimeError(f"unsupported database dialect: {dialect_name}")
            await session.execute(ensure_settings)

            counter_result = await session.execute(
                update(TicketSettings)
                .where(TicketSettings.guild_id == guild_id)
                .values(ticket_counter=TicketSettings.ticket_counter + 1)
                .returning(TicketSettings.ticket_counter, TicketSettings.ticket_limit)
            )
            number, ticket_limit = counter_result.one()

            open_count = await session.scalar(
                select(func.count())
                .select_from(Ticket)
                .where(
                    Ticket.guild_id == guild_id,
                    Ticket.owner_id == owner_id,
                    Ticket.open.is_(True),
                )
            )
            if int(open_count or 0) >= int(ticket_limit):
                raise TicketLimitReachedError(int(ticket_limit))

            ticket = Ticket(
                guild_id=guild_id,
                number=int(number),
                channel_id=None,
                owner_id=owner_id,
                panel_id=panel_id,
                open=True,
            )
            session.add(ticket)
            await session.flush()
            return ticket

    async def finalize_ticket(self, ticket_id: int, channel_id: int) -> None:
        async with self._database.session() as session, session.begin():
            ticket = await session.get(Ticket, ticket_id)
            if ticket is None:
                raise RuntimeError(f"ticket reservation {ticket_id} disappeared")
            ticket.channel_id = channel_id
            ticket.last_message_time = datetime.now(UTC)

    async def abandon_reservation(self, ticket_id: int) -> None:
        async with self._database.session() as session, session.begin():
            ticket = await session.get(Ticket, ticket_id)
            if ticket is not None and ticket.channel_id is None:
                await session.delete(ticket)

    async def get_ticket_by_channel(self, channel_id: int) -> Ticket | None:
        async with self._database.session() as session:
            return await session.scalar(select(Ticket).where(Ticket.channel_id == channel_id))

    async def transfer_owner(self, channel_id: int, owner_id: int) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                update(Ticket).where(Ticket.channel_id == channel_id).values(owner_id=owner_id)
            )

    async def set_claim(self, channel_id: int, staff_id: int | None) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                update(Ticket).where(Ticket.channel_id == channel_id).values(claimed_by=staff_id)
            )

    async def close_ticket(self, channel_id: int, reason: str | None) -> bool:
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                update(Ticket)
                .where(Ticket.channel_id == channel_id, Ticket.open.is_(True))
                .values(open=False, close_time=datetime.now(UTC), close_reason=reason)
            )
            return bool(result.rowcount)

    async def touch(self, channel_id: int, now: datetime | None = None) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                update(Ticket)
                .where(Ticket.channel_id == channel_id, Ticket.open.is_(True))
                .values(last_message_time=now or datetime.now(UTC))
            )

    async def inactive_tickets(self, now: datetime) -> list[Ticket]:
        async with self._database.session() as session:
            rows = await session.execute(
                select(Ticket, TicketSettings.autoclose_hours)
                .join(TicketSettings, TicketSettings.guild_id == Ticket.guild_id)
                .where(
                    Ticket.open.is_(True),
                    Ticket.excluded_autoclose.is_(False),
                    TicketSettings.autoclose_hours > 0,
                )
            )
            return [
                ticket
                for ticket, hours in rows.all()
                if ensure_utc(ticket.last_message_time) + timedelta(hours=hours) <= ensure_utc(now)
            ]

    async def exclude_autoclose(self, channel_id: int) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                update(Ticket)
                .where(Ticket.channel_id == channel_id)
                .values(excluded_autoclose=True)
            )

    async def add_staff(self, guild_id: int, entity_id: int, is_role: bool, type_: str) -> None:
        async with self._database.session() as session, session.begin():
            key = (guild_id, entity_id, type_)
            row = await session.get(TicketStaff, key)
            if row is None:
                session.add(
                    TicketStaff(
                        guild_id=guild_id,
                        entity_id=entity_id,
                        is_role=is_role,
                        type=type_,
                    )
                )
            else:
                row.is_role = is_role

    async def remove_staff(self, guild_id: int, entity_id: int, type_: str) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                delete(TicketStaff).where(
                    TicketStaff.guild_id == guild_id,
                    TicketStaff.entity_id == entity_id,
                    TicketStaff.type == type_,
                )
            )

    async def staff(self, guild_id: int) -> list[TicketStaff]:
        async with self._database.session() as session:
            return list(
                await session.scalars(select(TicketStaff).where(TicketStaff.guild_id == guild_id))
            )

    async def blacklist(self, guild_id: int) -> list[TicketBlacklist]:
        async with self._database.session() as session:
            return list(
                await session.scalars(
                    select(TicketBlacklist).where(TicketBlacklist.guild_id == guild_id)
                )
            )

    async def toggle_blacklist(self, guild_id: int, entity_id: int, is_role: bool) -> bool:
        async with self._database.session() as session, session.begin():
            row = await session.get(TicketBlacklist, (guild_id, entity_id))
            if row:
                await session.delete(row)
                return False
            session.add(
                TicketBlacklist(guild_id=guild_id, entity_id=entity_id, is_role=is_role)
            )
            return True

    async def create_panel(
        self,
        *,
        guild_id: int,
        title: str,
        content: str,
        color: int,
        category_id: int,
        button_label: str,
        button_emoji: str | None,
        welcome_message: str | None,
        mention_on_open: list[int],
    ) -> int:
        async with self._database.session() as session, session.begin():
            panel = TicketPanel(
                guild_id=guild_id,
                title=title,
                content=content,
                color=color,
                category_id=category_id,
                button_label=button_label,
                button_emoji=button_emoji,
                welcome_message=welcome_message,
                mention_on_open=json.dumps(mention_on_open),
            )
            session.add(panel)
            await session.flush()
            return panel.panel_id

    async def get_panel(self, panel_id: int, guild_id: int | None = None) -> TicketPanel | None:
        async with self._database.session() as session:
            panel = await session.get(TicketPanel, panel_id)
            if panel is None or (guild_id is not None and panel.guild_id != guild_id):
                return None
            return panel

    async def panel_by_message(self, guild_id: int, message_id: int) -> TicketPanel | None:
        async with self._database.session() as session:
            return await session.scalar(
                select(TicketPanel).where(
                    TicketPanel.guild_id == guild_id, TicketPanel.message_id == message_id
                )
            )

    async def panels(self, guild_id: int) -> list[TicketPanel]:
        async with self._database.session() as session:
            return list(
                await session.scalars(
                    select(TicketPanel)
                    .where(TicketPanel.guild_id == guild_id)
                    .order_by(TicketPanel.panel_id)
                )
            )

    async def set_panel_message(
        self, guild_id: int, panel_id: int, channel_id: int, message_id: int
    ) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                update(TicketPanel)
                .where(
                    TicketPanel.guild_id == guild_id,
                    TicketPanel.panel_id == panel_id,
                )
                .values(channel_id=channel_id, message_id=message_id)
            )

    async def update_panel(
        self, guild_id: int, panel_id: int, **values: str | int | None
    ) -> bool:
        allowed = {"title", "content", "button_label", "welcome_message", "color"}
        updates = {key: value for key, value in values.items() if key in allowed and value is not None}
        if not updates:
            return False
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                update(TicketPanel)
                .where(
                    TicketPanel.guild_id == guild_id,
                    TicketPanel.panel_id == panel_id,
                )
                .values(**updates)
            )
            return bool(result.rowcount)

    async def delete_panel(self, guild_id: int, panel_id: int) -> bool:
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                delete(TicketPanel).where(
                    TicketPanel.guild_id == guild_id,
                    TicketPanel.panel_id == panel_id,
                )
            )
            return bool(result.rowcount)

    async def add_member(self, channel_id: int, user_id: int) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(TicketMember, (channel_id, user_id))
            if row is None:
                session.add(TicketMember(channel_id=channel_id, user_id=user_id))

    async def remove_member(self, channel_id: int, user_id: int) -> None:
        async with self._database.session() as session, session.begin():
            await session.execute(
                delete(TicketMember).where(
                    TicketMember.channel_id == channel_id, TicketMember.user_id == user_id
                )
            )

    async def members(self, channel_id: int) -> list[int]:
        async with self._database.session() as session:
            rows = await session.scalars(
                select(TicketMember.user_id).where(TicketMember.channel_id == channel_id)
            )
            return list(rows)

    async def put_tag(self, guild_id: int, tag_id: str, content: str) -> None:
        async with self._database.session() as session, session.begin():
            row = await session.get(TicketTag, (guild_id, tag_id))
            if row:
                row.content = content
            else:
                session.add(TicketTag(guild_id=guild_id, tag_id=tag_id, content=content))

    async def delete_tag(self, guild_id: int, tag_id: str) -> bool:
        async with self._database.session() as session, session.begin():
            result = await session.execute(
                delete(TicketTag).where(
                    TicketTag.guild_id == guild_id, TicketTag.tag_id == tag_id
                )
            )
            return bool(result.rowcount)

    async def get_tag(self, guild_id: int, tag_id: str) -> str | None:
        async with self._database.session() as session:
            row = await session.get(TicketTag, (guild_id, tag_id))
            return row.content if row else None

    async def tags(self, guild_id: int) -> list[str]:
        async with self._database.session() as session:
            values = await session.scalars(
                select(TicketTag.tag_id)
                .where(TicketTag.guild_id == guild_id)
                .order_by(TicketTag.tag_id)
            )
            return list(values)
