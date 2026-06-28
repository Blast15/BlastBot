"""Ticket module - Hệ thống ticket hỗ trợ server."""

from .autoclose import TicketAutoclose
from .panel import TicketPanel
from .setup import TicketSetup
from .tags import TicketTags
from .ticket_cmds import TicketCommands


async def setup(bot):
    """Load all ticket cogs"""
    for cog_cls in (
        TicketSetup,
        TicketPanel,
        TicketCommands,
        TicketTags,
        TicketAutoclose,
    ):
        if bot.get_cog(cog_cls.__name__) is None:
            await bot.add_cog(cog_cls(bot))
