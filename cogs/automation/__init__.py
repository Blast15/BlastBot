"""Automation module - Welcome/goodbye, auto-message và các tác vụ tự động."""

from .auto_message import AutoMessage
from .greetings import Greetings


async def setup(bot):
    """Load all automation cogs"""
    for cog_cls in (Greetings, AutoMessage):
        if bot.get_cog(cog_cls.__name__) is None:
            await bot.add_cog(cog_cls(bot))
