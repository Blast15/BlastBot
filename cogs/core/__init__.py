"""Core commands - Essential bot features"""

from .help import HelpCommand


async def setup(bot):
    """Load core commands"""
    await bot.add_cog(HelpCommand(bot))
