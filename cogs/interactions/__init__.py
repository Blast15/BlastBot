"""Interactions module - Context menus and modals"""

from .context_menus import ContextMenus


async def setup(bot):
    """Load all interaction commands"""
    await bot.add_cog(ContextMenus(bot))
