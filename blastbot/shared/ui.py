from __future__ import annotations

import logging

import discord

from blastbot.core.errors import UserFacingError
from blastbot.shared.embeds import error as error_embed

logger = logging.getLogger(__name__)


async def respond_ui_error(interaction: discord.Interaction, exception: Exception) -> None:
    message = exception.user_message if isinstance(exception, UserFacingError) else "Đã xảy ra lỗi nội bộ. Vui lòng thử lại sau."
    if not isinstance(exception, UserFacingError):
        logger.exception(
            "Unhandled UI interaction error",
            exc_info=exception,
            extra={
                "guild_id": interaction.guild_id,
                "channel_id": interaction.channel_id,
                "user_id": interaction.user.id,
                "interaction_id": interaction.id,
                "error_type": type(exception).__name__,
            },
        )
    payload = {"embed": error_embed("Không thể thực hiện", message), "ephemeral": True}
    if interaction.response.is_done():
        await interaction.followup.send(**payload)
    else:
        await interaction.response.send_message(**payload)


class SafeView(discord.ui.View):
    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[discord.ui.View],
    ) -> None:
        await respond_ui_error(interaction, error)


class SafeModal(discord.ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await respond_ui_error(interaction, error)
