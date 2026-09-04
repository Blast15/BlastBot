from __future__ import annotations

import string
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
        validated_message = validate_greeting_template(
            message, maximum=4000 if use_embed else 2000
        )
        await self.repository.configure_greeting(
            guild_id=guild_id,
            kind=kind,
            channel_id=channel_id,
            use_embed=use_embed,
            title=require_text(title, maximum=256) if title else None,
            message=validated_message,
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
        interval = require_range(
            interval_minutes,
            minimum=self.MIN_INTERVAL_MINUTES,
            maximum=self.MAX_INTERVAL_MINUTES,
            name="Chu kỳ",
        )
        text = require_text(content, maximum=4000 if use_embed else 2000)
        auto_id = await self.repository.create_auto_message_bounded(
            guild_id=guild_id,
            channel_id=channel_id,
            content=text,
            interval_minutes=interval,
            use_embed=use_embed,
            limit=self.MAX_AUTO_MESSAGES,
        )
        if auto_id is None:
            raise ConflictError(
                "auto-message limit reached",
                f"Server đã đạt giới hạn {self.MAX_AUTO_MESSAGES} auto-message.",
            )
        return auto_id

    async def remove_auto_message(self, guild_id: int, auto_id: int) -> None:
        if not await self.repository.delete_auto_message(guild_id, auto_id):
            raise ResourceNotFoundError("auto-message not found", "Không tìm thấy auto-message.")

    async def set_auto_message_enabled(self, guild_id: int, auto_id: int, enabled: bool) -> None:
        if not await self.repository.toggle_auto_message(guild_id, auto_id, enabled):
            raise ResourceNotFoundError("auto-message not found", "Không tìm thấy auto-message.")


GREETING_FIELDS = frozenset({"user", "user_mention", "user_name", "server", "member_count"})


def validate_greeting_template(template: str, *, maximum: int) -> str:
    """Validate fields without formatting, so hostile specs cannot allocate output."""
    text = require_text(template, maximum=maximum)
    try:
        parsed = tuple(string.Formatter().parse(text))
    except ValueError as exc:
        raise ValidationError(
            "malformed greeting template", "Template lời chào không hợp lệ."
        ) from exc
    for _, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if field_name not in GREETING_FIELDS:
            raise ValidationError(
                f"unknown greeting placeholder: {field_name!r}",
                f"Placeholder `{{{field_name}}}` không được hỗ trợ.",
            )
        if format_spec:
            raise ValidationError(
                "greeting format spec is not allowed",
                "Template lời chào không cho phép format spec.",
            )
        if conversion:
            raise ValidationError(
                "greeting conversion is not allowed",
                "Template lời chào không cho phép conversion.",
            )
    return text
