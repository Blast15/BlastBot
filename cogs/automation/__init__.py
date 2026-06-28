"""Automation module - Welcome/goodbye, auto-message và các tác vụ tự động."""

from .greetings import Greetings
from .auto_message import AutoMessage


async def setup(bot):
    """Load all automation cogs"""
    await bot.add_cog(Greetings(bot))
    await bot.add_cog(AutoMessage(bot))
