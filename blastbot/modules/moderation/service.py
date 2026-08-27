from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from blastbot.modules.moderation.repository import ModerationRepository
from blastbot.shared.validation import require_range, require_text


@dataclass(frozen=True, slots=True)
class ModerationRecord:
    guild_id: int
    moderator_id: int
    target_id: int
    target_str: str | None
    reason: str | None


class ModerationService:
    def __init__(self, repository: ModerationRepository) -> None:
        self.repository = repository

    async def record_action(self, action: str, record: ModerationRecord, **extra: Any) -> None:
        reason = require_text(record.reason, maximum=1000) if record.reason else None
        await self.repository.add_log(
            guild_id=record.guild_id,
            moderator_id=record.moderator_id,
            action=action.upper(),
            target_id=record.target_id,
            target_str=record.target_str,
            reason=reason,
            extra=extra or None,
        )

    async def warn(self, record: ModerationRecord) -> int:
        reason = require_text(record.reason, maximum=1000) if record.reason else None
        return await self.repository.add_warning_with_log(
            guild_id=record.guild_id,
            user_id=record.target_id,
            moderator_id=record.moderator_id,
            target_str=record.target_str,
            reason=reason,
        )

    async def warnings(self, guild_id: int, user_id: int) -> int:
        return await self.repository.get_warnings(guild_id, user_id)

    async def add_temp_role(
        self, *, guild_id: int, user_id: int, role_id: int, duration_minutes: int
    ) -> datetime:
        minutes = require_range(duration_minutes, minimum=1, maximum=40320, name="Thời lượng")
        expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
        await self.repository.put_temp_role(
            guild_id=guild_id,
            user_id=user_id,
            role_id=role_id,
            expires_at=expires_at,
        )
        return expires_at
