"""Embed templates và helpers"""

import discord
from datetime import datetime
from typing import Optional
from .constants import COLORS, EMOJIS, BOT_INFO


def create_embed(
    title: Optional[str] = None,
    description: Optional[str] = None,
    color: int = COLORS['primary'],
    thumbnail: Optional[str] = None,
    image: Optional[str] = None,
    author_name: Optional[str] = None,
    author_icon: Optional[str] = None,
    footer_text: Optional[str] = None,
    footer_icon: Optional[str] = None,
    timestamp: bool = True
) -> discord.Embed:
    """Tạo embed cơ bản với các tham số tùy chỉnh"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow() if timestamp else None
    )
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
    
    if author_name:
        embed.set_author(name=author_name, icon_url=author_icon)
    
    if footer_text:
        embed.set_footer(text=footer_text, icon_url=footer_icon)
    
    return embed


def success_embed(title: str, description: Optional[str] = None) -> discord.Embed:
    """Embed cho thông báo thành công"""
    return create_embed(
        title=f"{EMOJIS['success']} {title}",
        description=description,
        color=COLORS['success']
    )


def error_embed(title: str, description: Optional[str] = None) -> discord.Embed:
    """Embed cho thông báo lỗi"""
    return create_embed(
        title=f"{EMOJIS['error']} {title}",
        description=description,
        color=COLORS['error']
    )


def warning_embed(title: str, description: Optional[str] = None) -> discord.Embed:
    """Embed cho cảnh báo"""
    return create_embed(
        title=f"{EMOJIS['warning']} {title}",
        description=description,
        color=COLORS['warning']
    )


def info_embed(title: str, description: Optional[str] = None) -> discord.Embed:
    """Embed cho thông tin"""
    return create_embed(
        title=f"{EMOJIS['info']} {title}",
        description=description,
        color=COLORS['info']
    )


def bot_info_embed(bot: discord.Client) -> discord.Embed:
    """Embed hiển thị thông tin bot"""
    embed = create_embed(
        title=f"Thông tin về {BOT_INFO['name']}",
        description=BOT_INFO['description'],
        color=COLORS['primary'],
        thumbnail=bot.user.avatar.url if bot.user and bot.user.avatar else None
    )
    
    embed.add_field(name="📊 Servers", value=str(len(bot.guilds)), inline=True)
    embed.add_field(name="👥 Users", value=str(len(bot.users)), inline=True)
    embed.add_field(name="📡 Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="🔖 Version", value=BOT_INFO['version'], inline=True)
    embed.add_field(name="🐍 Discord.py", value=discord.__version__, inline=True)
    embed.add_field(name="👨‍💻 Developer", value=BOT_INFO['author'], inline=True)
    
    embed.set_footer(text=f"Bot ID: {bot.user.id}" if bot.user else "Bot")
    
    return embed


def user_info_embed(user: discord.User | discord.Member) -> discord.Embed:
    """Embed hiển thị thông tin user"""
    embed = create_embed(
        title=f"Thông tin về {user.name}",
        color=COLORS['info'],
        thumbnail=user.display_avatar.url
    )
    
    embed.add_field(name="👤 Username", value=str(user), inline=True)
    embed.add_field(name="🆔 ID", value=user.id, inline=True)
    embed.add_field(name="🤖 Bot", value="Có" if user.bot else "Không", inline=True)
    embed.add_field(
        name="📅 Tạo tài khoản",
        value=f"<t:{int(user.created_at.timestamp())}:F>",
        inline=False
    )
    
    # Thêm thông tin member nếu có
    if isinstance(user, discord.Member):
        if user.joined_at:
            embed.add_field(
                name="📥 Tham gia server",
                value=f"<t:{int(user.joined_at.timestamp())}:F>",
                inline=False
            )
        
        if user.roles[1:]:  # Skip @everyone role
            roles = ", ".join([role.mention for role in user.roles[1:][:10]])
            if len(user.roles) > 11:
                roles += f" và {len(user.roles) - 11} vai trò khác..."
            embed.add_field(name="🎭 Vai trò", value=roles, inline=False)
    
    return embed
