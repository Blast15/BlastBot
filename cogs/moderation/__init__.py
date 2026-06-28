"""Moderation module - Các lệnh quản lý server"""

from .ban import BanCommand
from .clear import ClearCommand
from .kick import KickCommand
from .softban import SoftbanCommand
from .temprole import TempRoleCommand
from .timeout import TimeoutCommand
from .warn import WarnCommand


async def setup(bot):
    """Load all moderation commands"""
    for cog_cls in (
        KickCommand,
        BanCommand,
        TimeoutCommand,
        ClearCommand,
        WarnCommand,
        SoftbanCommand,
        TempRoleCommand,
    ):
        if bot.get_cog(cog_cls.__name__) is None:
            await bot.add_cog(cog_cls(bot))
