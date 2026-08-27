from __future__ import annotations

from dataclasses import dataclass

from blastbot.core.errors import ConflictError, ResourceNotFoundError, ValidationError
from blastbot.modules.automation.repository import AutomationRepository
from blastbot.shared.validation import require_range, require_text


@dataclass(frozen=True, slots=True)
class GreetingTemplate:
    title: str | None
    message: str
    use_embed: bool
    color: int | None


class AutomationService:
    MIN_INTERVAL_MINUTES = 5
    MAX_INTERVAL_MINUTES = 10080
    MAX_AUTO_MESSAGES = 20

    def __init__(self, repository: AutomationRepository) -> None:
        self.repository = repository

    async def configure_greeting(
        self,
        *,
        guild_id: int,
        kind: str,
        channel_id: int,
        message: str,
        use_embed: bool = True,
        title: str | None = None,
        color: int | None = None,
    ) -> None:
        if kind not in {"welcome", "goodbye"}:
            raise ValidationError("invalid greeting kind")
        await self.repository.configure_greeting(
            guild_id=guild_id,
            kind=kind,
            channel_id=channel_id,
            use_embed=use_embed,
            title=require_text(title, maximum=256) if title else None,
            message=require_text(message, maximum=4000 if use_embed else 2000),
            color=color,
        )

    async def disable_greeting(self, guild_id: int, kind: str) -> None:
        if kind not in {"welcome", "goodbye"}:
            raise ValidationError("invalid greeting kind")
        await self.repository.set_greeting_enabled(guild_id, kind, False)

    async def add_auto_message(
        self,
        *,
        guild_id: int,
        channel_id: int,
        content: str,
        interval_minutes: int,
        use_embed: bool,
    ) -> int:
        existing = await self.repository.list_auto_messages(guild_id)
        if len(existing) >= self.MAX_AUTO_MESSAGES:
            raise ConflictError(
                "auto-message limit reached",
                f"Server đã đạt giới hạn {self.MAX_AUTO_MESSAGES} auto-message.",
            )
        interval = require_range(
            interval_minutes,
            minimum=self.MIN_INTERVAL_MINUTES,
            maximum=self.MAX_INTERVAL_MINUTES,
            name="Chu kỳ",
        )
        text = require_text(content, maximum=4000 if use_embed else 2000)
        return await self.repository.create_auto_message(
            guild_id=guild_id,
            channel_id=channel_id,
            content=text,
            interval_minutes=interval,
            use_embed=use_embed,
        )

    async def remove_auto_message(self, guild_id: int, auto_id: int) -> None:
        if not await self.repository.delete_auto_message(guild_id, auto_id):
            raise ResourceNotFoundError(
                "auto-message not found", "Không tìm thấy auto-message."
            )

    async def set_auto_message_enabled(
        self, guild_id: int, auto_id: int, enabled: bool
    ) -> None:
        if not await self.repository.toggle_auto_message(guild_id, auto_id, enabled):
            raise ResourceNotFoundError(
                "auto-message not found", "Không tìm thấy auto-message."
            )
