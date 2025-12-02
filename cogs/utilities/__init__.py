"""Utilities module - Role management commands"""

from .roles import RolesCommand


async def setup(bot):
    """Load all utility commands"""
    await bot.add_cog(RolesCommand(bot))
