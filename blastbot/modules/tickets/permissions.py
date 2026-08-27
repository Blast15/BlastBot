from __future__ import annotations

import discord

from blastbot.database.models import TicketStaff


def member_matches_entity(member: discord.Member, entity_id: int, is_role: bool) -> bool:
    if is_role:
        return any(role.id == entity_id for role in member.roles)
    return member.id == entity_id


def is_ticket_staff(member: discord.Member, staff: list[TicketStaff]) -> bool:
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True
    return any(member_matches_entity(member, item.entity_id, item.is_role) for item in staff)


def is_blacklisted(member: discord.Member, blacklist: list[object]) -> bool:
    return any(
        member_matches_entity(
            member,
            int(getattr(item, "entity_id")),
            bool(getattr(item, "is_role")),
        )
        for item in blacklist
    )


def ticket_overwrites(
    guild: discord.Guild,
    owner: discord.Member,
    bot_member: discord.Member,
    staff: list[TicketStaff],
) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
    overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        owner: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True,
            read_message_history=True,
        ),
    }
    for item in staff:
        target: discord.Role | discord.Member | None
        if item.is_role:
            target = guild.get_role(item.entity_id)
        else:
            target = guild.get_member(item.entity_id)
        if target is not None:
            overwrites[target] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
            )
    return overwrites
