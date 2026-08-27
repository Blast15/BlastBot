from __future__ import annotations

from blastbot.modules.feedback.repository import FeedbackRepository
from blastbot.shared.validation import require_text


class FeedbackService:
    def __init__(self, repository: FeedbackRepository) -> None:
        self.repository = repository

    def validate_suggestion(self, text: str) -> str:
        return require_text(text, maximum=1000)

    def validate_report(self, reason: str, details: str) -> tuple[str, str]:
        return require_text(reason, maximum=100), require_text(details, maximum=1000)

    async def register_suggestion(self, guild_id: int, message_id: int) -> None:
        await self.repository.register_message(guild_id, message_id)

    async def vote(self, message_id: int, user_id: int, vote: int) -> tuple[int, int]:
        if vote not in {-1, 1}:
            raise ValueError("vote must be -1 or 1")
        return await self.repository.toggle_vote(message_id, user_id, vote)
