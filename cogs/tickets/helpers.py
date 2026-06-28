"""Helper dùng chung cho ticket cogs."""

import discord


async def is_ticket_staff(bot, member: discord.Member) -> bool:
    """Admin server, hoặc nằm trong staff support/admin của ticket."""
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True
    db = getattr(bot, "db", None)
    if db is None:
        return False
    staff = await db.get_staff(member.guild.id)
    member_role_ids = {r.id for r in member.roles}
    for entry in staff:
        if entry["is_role"] and entry["entity_id"] in member_role_ids:
            return True
        if not entry["is_role"] and entry["entity_id"] == member.id:
            return True
    return False


async def is_blacklisted(bot, member: discord.Member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return False
    db = getattr(bot, "db", None)
    if db is None:
        return False
    bl = await db.get_blacklist(member.guild.id)
    member_role_ids = {r.id for r in member.roles}
    for entry in bl:
        if entry["is_role"] and entry["entity_id"] in member_role_ids:
            return True
        if not entry["is_role"] and entry["entity_id"] == member.id:
            return True
    return False
