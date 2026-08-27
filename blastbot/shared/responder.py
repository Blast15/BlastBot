from __future__ import annotations

import logging

import discord

logger = logging.getLogger(__name__)


async def send_interaction(
    interaction: discord.Interaction,
    *,
    content: str | None = None,
    embed: discord.Embed | None = None,
    ephemeral: bool = False,
    view: discord.ui.View | None = None,
) -> None:
    """Send exactly once, choosing initial response or follow-up safely."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                content=content, embed=embed, ephemeral=ephemeral, view=view
            )
        else:
            await interaction.response.send_message(
                content=content, embed=embed, ephemeral=ephemeral, view=view
            )
    except discord.NotFound:
        logger.warning(
            "Interaction expired before response",
            extra={"interaction_id": interaction.id, "user_id": interaction.user.id},
        )
