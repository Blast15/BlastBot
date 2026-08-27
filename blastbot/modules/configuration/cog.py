from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from blastbot.core.bot import BlastBot
from blastbot.shared.embeds import info, success
from blastbot.shared.permissions import require_guild_permissions


class ConfigurationCog(commands.Cog):
    config = app_commands.Group(
        name="config",
        description="Cấu hình chung của BlastBot",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot

    @config.command(
        name="logchannel", description="Đặt hoặc tắt channel nhận moderation/report log"
    )
    @require_guild_permissions(manage_guild=True)
    async def log_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.guild_config.set_log_channel(
            interaction.guild_id, channel.id if channel else None
        )
        text = f"Log channel: {channel.mention}." if channel else "Đã tắt log channel."
        await interaction.response.send_message(embed=success("Đã cập nhật", text), ephemeral=True)

    @config.command(name="view", description="Xem cấu hình chung")
    @require_guild_permissions(manage_guild=True)
    async def view(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        data = await self.bot.app.guild_config.get(interaction.guild_id)
        log_channel = f"<#{data.log_channel_id}>" if data.log_channel_id else "Chưa cấu hình"
        await interaction.response.send_message(
            embed=info("Cấu hình BlastBot", f"**Kênh moderation/report:** {log_channel}"),
            ephemeral=True,
        )


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(ConfigurationCog(bot))
