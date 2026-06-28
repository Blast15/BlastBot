"""Utilities module - Role management commands"""

from .feedback import Feedback
from .roles import RolesCommand


async def setup(bot):
    """Load all utility commands"""
    await bot.add_cog(RolesCommand(bot))
    await bot.add_cog(Feedback(bot))
