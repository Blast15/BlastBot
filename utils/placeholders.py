"""Thay thế placeholder trong message greeting."""

import discord


def render_placeholders(text: str, member: discord.Member) -> str:
    """Hỗ trợ: {user}, {user_mention}, {user_name}, {server}, {member_count}."""
    if not text:
        return text
    guild = member.guild
    replacements = {
        "{user}": str(member),
        "{user_mention}": member.mention,
        "{user_name}": member.display_name,
        "{server}": guild.name,
        "{member_count}": str(guild.member_count or len(guild.members)),
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text
