"""Autoclose daemon loop cho tickets không hoạt động."""

import discord
from discord.ext import commands, tasks
import logging

from utils.constants import TICKET_CONFIG
from .views import perform_close

logger = logging.getLogger('BlastBot.Tickets.Autoclose')


class TicketAutoclose(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autoclose_check.start()

    def cog_unload(self):
        self.autoclose_check.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if not message.channel.name.startswith("ticket-"):
            return
        db = getattr(self.bot, 'db', None)
        if db is None:
            return
        ticket = await db.get_ticket_by_channel(message.channel.id)
        if ticket and ticket['open']:
            await db.touch_ticket(message.channel.id)

    @tasks.loop(minutes=TICKET_CONFIG['autoclose_check_minutes'])
    async def autoclose_check(self):
        db = getattr(self.bot, 'db', None)
        if db is None:
            return

        try:
            # We check all inactive tickets across guilds
            inactive_tickets = await db.get_inactive_tickets()
            for t in inactive_tickets:
                guild = self.bot.get_guild(t['guild_id'])
                if not guild:
                    continue
                channel = guild.get_channel(t['channel_id'])
                if isinstance(channel, discord.TextChannel):
                    logger.info(f"Tự động đóng ticket #{t['number']} ({channel.id}) do không hoạt động.")
                    await perform_close(self.bot, channel, self.bot.user, reason="Tự động đóng do không hoạt động")
        except Exception as e:
            logger.error(f"Lỗi khi chạy autoclose check: {e}", exc_info=True)

    @autoclose_check.before_loop
    async def before_autoclose(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TicketAutoclose(bot))
