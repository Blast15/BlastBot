from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from blastbot.core.errors import UserFacingError
from blastbot.shared.embeds import error as error_embed
from blastbot.shared.responder import send_interaction

logger = logging.getLogger(__name__)


async def handle_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    original = getattr(error, "original", error)
    if isinstance(error, app_commands.CommandOnCooldown):
        message = f"Bạn đang dùng lệnh quá nhanh. Thử lại sau {error.retry_after:.1f}s."
    elif isinstance(error, app_commands.MissingPermissions):
        message = "Bạn không có đủ quyền để thực hiện lệnh này."
    elif isinstance(error, app_commands.BotMissingPermissions):
        message = "Bot không có đủ quyền để thực hiện hành động này."
    elif isinstance(error, app_commands.NoPrivateMessage):
        message = "Lệnh này chỉ dùng trong server."
    elif isinstance(original, UserFacingError):
        message = original.user_message
    else:
        logger.exception(
            "Unhandled application command error",
            exc_info=original,
            extra={
                "guild_id": interaction.guild_id,
                "channel_id": interaction.channel_id,
                "user_id": interaction.user.id,
                "interaction_id": interaction.id,
                "command": interaction.command.name if interaction.command else None,
                "error_type": type(original).__name__,
            },
        )
        message = "Đã xảy ra lỗi nội bộ. Vui lòng thử lại sau."
    await send_interaction(
        interaction,
        embed=error_embed("Không thể thực hiện", message),
        ephemeral=True,
    )


class PrefixErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context[commands.Bot], error: Exception) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Thử lại sau {error.retry_after:.1f}s.")
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Bạn không có đủ quyền.")
            return
        logger.exception("Unhandled prefix command error", exc_info=error)
