from __future__ import annotations

import discord

from blastbot import __version__

PRIMARY = 0x5865F2
SUCCESS = 0x57F287
WARNING = 0xFEE75C
ERROR = 0xED4245
INFO = 0x3498DB


def embed(
    title: str, description: str | None = None, *, color: int = PRIMARY
) -> discord.Embed:
    card = discord.Embed(title=title, description=description, color=color)
    card.set_footer(text=f"BlastBot v{__version__}")
    return card


def success(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, color=SUCCESS)


def error(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, color=ERROR)


def warning(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, color=WARNING)


def info(title: str, description: str | None = None) -> discord.Embed:
    return embed(title, description, color=INFO)
