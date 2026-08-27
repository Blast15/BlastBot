from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import discord
from discord import app_commands

CheckPredicate = Callable[[discord.Interaction], Coroutine[Any, Any, bool]]


def require_guild_permissions(**permissions: bool) -> Callable[[Any], Any]:
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.NoPrivateMessage()
        missing = [
            name
            for name, required in permissions.items()
            if required and not getattr(interaction.user.guild_permissions, name, False)
        ]
        if missing:
            raise app_commands.MissingPermissions(missing)
        return True

    return app_commands.check(predicate)


def validate_moderation_target(
    guild: discord.Guild,
    moderator: discord.Member,
    target: discord.Member,
) -> str | None:
    if target.id == moderator.id:
        return "Bạn không thể thực hiện hành động này với chính mình."
    if target.bot:
        return "Không thể thực hiện hành động này với bot."
    if target.id == guild.owner_id:
        return "Không thể thực hiện hành động này với chủ server."
    if moderator.id != guild.owner_id and target.top_role >= moderator.top_role:
        return "Member có role cao hơn hoặc bằng highest role của bạn."
    bot_member = guild.me
    if bot_member is None or target.top_role >= bot_member.top_role:
        return "Bot không thể thao tác member này do role hierarchy."
    return None


def validate_role_manage(
    guild: discord.Guild, actor: discord.Member, role: discord.Role
) -> str | None:
    if role.is_default():
        return "Không thể quản lý @everyone."
    if role.managed:
        return "Role này do integration quản lý."
    if actor.id != guild.owner_id and role >= actor.top_role:
        return "Role cao hơn hoặc bằng highest role của bạn."
    bot_member = guild.me
    if bot_member is None or role >= bot_member.top_role:
        return "Bot không thể quản lý role này do role hierarchy."
    return None


def validate_member_manage(
    guild: discord.Guild, actor: discord.Member, target: discord.Member
) -> str | None:
    if target.id == guild.owner_id and actor.id != guild.owner_id:
        return "Không thể quản lý role của chủ server."
    if actor.id != guild.owner_id and target.id != actor.id and target.top_role >= actor.top_role:
        return "Không thể quản lý role của thành viên có role cao hơn hoặc ngang bạn."
    return None
