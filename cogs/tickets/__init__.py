"""Ticket module - Hệ thống ticket hỗ trợ server."""

from .setup import TicketSetup
from .panel import TicketPanel
from .ticket_cmds import TicketCommands
from .tags import TicketTags
from .autoclose import TicketAutoclose


async def setup(bot):
    """Load all ticket cogs"""
    await bot.add_cog(TicketSetup(bot))
    await bot.add_cog(TicketPanel(bot))
    await bot.add_cog(TicketCommands(bot))
    await bot.add_cog(TicketTags(bot))
    await bot.add_cog(TicketAutoclose(bot))
