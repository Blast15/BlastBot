import discord
from typing import Optional, Union
from .constants import Colors

def create_error_embed(message: str, title: Optional[str] = None) -> discord.Embed:
    """Creates an error embed with red color.
    
    Args:
        message: The error message to display
        title: Optional title for the embed
    
    Returns:
        A formatted discord.Embed for error messages
    """
    embed = discord.Embed(
        description=message,
        color=Colors.ERROR
    )
    if title:
        embed.title = title
    return embed

def create_success_embed(message: str, title: Optional[str] = None) -> discord.Embed:
    """Creates a success embed with green color.
    
    Args:
        message: The success message to display
        title: Optional title for the embed
    
    Returns:
        A formatted discord.Embed for success messages
    """
    embed = discord.Embed(
        description=message,
        color=Colors.SUCCESS
    )
    if title:
        embed.title = title
    return embed

def create_warning_embed(message: str, title: Optional[str] = None) -> discord.Embed:
    """Creates a warning embed with yellow color.
    
    Args:
        message: The warning message to display
        title: Optional title for the embed
    
    Returns:
        A formatted discord.Embed for warning messages
    """
    embed = discord.Embed(
        description=message,
        color=Colors.WARNING
    )
    if title:
        embed.title = "⚠️ " + (title or "Cảnh báo")
    return embed

def create_processing_embed(message: str, title: Optional[str] = None) -> discord.Embed:
    """Creates a processing embed with blurple color.
    
    Args:
        message: The processing message to display
        title: Optional title for the embed
    
    Returns:
        A formatted discord.Embed for processing messages
    """
    embed = discord.Embed(
        description=message,
        color=Colors.PRIMARY
    )
    if title:
        embed.title = title
    return embed

def create_mod_action_embed(
    target: Union[discord.Member, discord.User], 
    action: str, 
    moderator: discord.Member, 
    reason: str
) -> discord.Embed:
    """Creates a moderation action embed.
    
    Args:
        target: The user who received the moderation action
        action: The type of action (kick, ban, etc.)
        moderator: The moderator who performed the action
        reason: The reason for the action
    
    Returns:
        A formatted discord.Embed for moderation actions
    """
    embed = discord.Embed(
        title=f"🛡️ {action.title()} | {target.name}#{target.discriminator}",
        color=Colors.PRIMARY
    )
    
    embed.add_field(name="Người dùng", value=f"{target.mention} ({target.id})", inline=True)
    embed.add_field(name="Người quản trị", value=moderator.mention, inline=True)
    embed.add_field(name="Lý do", value=reason, inline=False)
    
    embed.set_thumbnail(url=target.display_avatar.url)
    
    return embed
