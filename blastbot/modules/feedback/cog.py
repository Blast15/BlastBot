from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from blastbot.core.bot import BlastBot
from blastbot.modules.feedback.ui import SuggestionModal


class FeedbackCog(commands.Cog):
    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot

    @app_commands.command(name="suggest", description="Gửi một góp ý cho server")
    @app_commands.guild_only()
    async def suggest(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(SuggestionModal(self.bot.app.feedback))


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(FeedbackCog(bot))
