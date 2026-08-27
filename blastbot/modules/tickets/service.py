from __future__ import annotations

import json
from dataclasses import dataclass

from blastbot.core.errors import ResourceNotFoundError, ValidationError
from blastbot.database.models import TicketPanel, TicketSettings
from blastbot.modules.tickets.repository import TicketRepository
from blastbot.shared.validation import normalize_tag_id, require_text


@dataclass(frozen=True, slots=True)
class TicketReservation:
    id: int
    number: int
    owner_id: int
    panel_id: int | None


@dataclass(frozen=True, slots=True)
class PanelData:
    panel_id: int
    guild_id: int
    title: str
    content: str
    color: int
    category_id: int
    button_label: str
    button_emoji: str | None
    welcome_message: str | None
    mention_on_open: tuple[int, ...]
    channel_id: int | None
    message_id: int | None


class TicketService:
    DEFAULT_COLOR = 0x5865F2
    MAX_LIMIT = 50

    def __init__(self, repository: TicketRepository) -> None:
        self.repository = repository

    @staticmethod
    def panel_data(panel: TicketPanel) -> PanelData:
        try:
            mentions = tuple(
                int(value) for value in json.loads(panel.mention_on_open or "[]")
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            mentions = ()
        return PanelData(
            panel_id=panel.panel_id,
            guild_id=panel.guild_id,
            title=panel.title,
            content=panel.content,
            color=panel.color,
            category_id=panel.category_id,
            button_label=panel.button_label,
            button_emoji=panel.button_emoji,
            welcome_message=panel.welcome_message,
            mention_on_open=mentions,
            channel_id=panel.channel_id,
            message_id=panel.message_id,
        )

    async def settings(self, guild_id: int) -> TicketSettings:
        return await self.repository.get_settings(guild_id)

    async def set_transcript_channel(self, guild_id: int, channel_id: int) -> None:
        await self.repository.update_settings(
            guild_id, transcript_channel_id=channel_id
        )

    async def set_limit(self, guild_id: int, amount: int) -> int:
        # Legacy behavior clamps rather than rejects out-of-range values.
        clamped = max(1, min(self.MAX_LIMIT, amount))
        await self.repository.update_settings(guild_id, ticket_limit=clamped)
        return clamped

    async def set_autoclose(self, guild_id: int, hours: int) -> int:
        # Preserve legacy /ticket autoclose semantics.
        clamped = max(0, min(720, hours))
        await self.repository.update_settings(guild_id, autoclose_hours=clamped)
        return clamped

    async def set_claim_mode(self, guild_id: int, mode: str) -> None:
        if mode not in {"reply_only", "view_all"}:
            raise ValidationError("invalid claim mode", "Claim mode không hợp lệ.")
        await self.repository.update_settings(guild_id, claim_mode=mode)

    async def reserve(
        self, guild_id: int, owner_id: int, panel_id: int | None
    ) -> TicketReservation:
        ticket = await self.repository.reserve_ticket(
            guild_id=guild_id, owner_id=owner_id, panel_id=panel_id
        )
        return TicketReservation(
            id=ticket.id,
            number=ticket.number,
            owner_id=ticket.owner_id,
            panel_id=ticket.panel_id,
        )

    async def finalize(self, reservation_id: int, channel_id: int) -> None:
        await self.repository.finalize_ticket(reservation_id, channel_id)

    async def abandon(self, reservation_id: int) -> None:
        await self.repository.abandon_reservation(reservation_id)

    async def create_panel(
        self,
        *,
        guild_id: int,
        category_id: int,
        title: str,
        content: str,
        button_label: str,
        mention_role_id: int | None,
    ) -> int:
        return await self.repository.create_panel(
            guild_id=guild_id,
            title=require_text(title, maximum=256),
            content=require_text(content, maximum=4000),
            color=self.DEFAULT_COLOR,
            category_id=category_id,
            button_label=require_text(button_label, maximum=80),
            button_emoji=None,
            welcome_message=None,
            mention_on_open=[mention_role_id] if mention_role_id else [],
        )

    async def get_panel(self, panel_id: int, guild_id: int) -> PanelData:
        panel = await self.repository.get_panel(panel_id, guild_id)
        if panel is None:
            raise ResourceNotFoundError("panel not found", "Không tìm thấy panel.")
        return self.panel_data(panel)

    async def panel_for_message(
        self, guild_id: int, message_id: int
    ) -> PanelData | None:
        panel = await self.repository.panel_by_message(guild_id, message_id)
        return self.panel_data(panel) if panel else None

    async def panels(self, guild_id: int) -> list[PanelData]:
        return [
            self.panel_data(panel) for panel in await self.repository.panels(guild_id)
        ]

    async def edit_panel(
        self,
        *,
        guild_id: int,
        panel_id: int,
        title: str | None,
        content: str | None,
        button_label: str | None,
    ) -> bool:
        return await self.repository.update_panel(
            guild_id,
            panel_id,
            title=require_text(title, maximum=256) if title else None,
            content=require_text(content, maximum=4000) if content else None,
            button_label=require_text(button_label, maximum=80)
            if button_label
            else None,
        )

    async def add_tag(self, guild_id: int, tag_id: str, content: str) -> str:
        normalized = normalize_tag_id(tag_id)
        await self.repository.put_tag(
            guild_id, normalized, require_text(content, maximum=2000)
        )
        return normalized

    async def delete_tag(self, guild_id: int, tag_id: str) -> bool:
        return await self.repository.delete_tag(guild_id, normalize_tag_id(tag_id))

    async def tag(self, guild_id: int, tag_id: str) -> str | None:
        return await self.repository.get_tag(guild_id, normalize_tag_id(tag_id))
