import discord
from discord.ext import commands
from discord import app_commands
import platform
import time
import psutil
import datetime
from typing import Optional

from utils.constants import Colors
from utils.embed_helpers import create_error_embed

class Info(commands.Cog):
    """Informational commands for the bot and server."""
    
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
    
    @commands.hybrid_command(name="ping", description="Kiểm tra độ trễ của bot")
    async def ping(self, ctx: commands.Context):
        """Check the bot's latency to Discord."""
        # Calculate websocket latency
        ws_latency = round(self.bot.latency * 1000)
        
        # Measure message latency
        start = time.perf_counter()
        message = await ctx.send("🏓 Pong!")
        end = time.perf_counter()
        message_latency = round((end - start) * 1000)
        
        # Create embed with latency information
        embed = discord.Embed(
            title="🏓 Pong!",
            color=Colors.INFO
        )
        
        embed.add_field(name="WebSocket Latency", value=f"{ws_latency}ms", inline=True)
        embed.add_field(name="Message Latency", value=f"{message_latency}ms", inline=True)
        
        await message.edit(content=None, embed=embed)
    
    @commands.hybrid_command(name="botinfo", description="Hiển thị thông tin về bot")
    async def botinfo(self, ctx: commands.Context):
        """Display information about the bot."""
        # Calculate uptime
        uptime = time.time() - self.start_time
        uptime_str = self.format_uptime(uptime)
        
        # Get memory usage
        memory = psutil.Process().memory_info().rss / 1024**2  # Convert to MB
        
        # Create embed
        embed = discord.Embed(
            title=f"📊 Thông tin về {self.bot.user.name}",
            color=Colors.INFO
        )
        
        # Bot information
        embed.add_field(name="Bot ID", value=str(self.bot.user.id), inline=True)
        embed.add_field(name="Phiên bản Discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Phiên bản Python", value=platform.python_version(), inline=True)
        
        # Performance stats
        embed.add_field(name="Thời gian hoạt động", value=uptime_str, inline=True)
        embed.add_field(name="Bộ nhớ đã dùng", value=f"{memory:.2f} MB", inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        
        # Server count
        embed.add_field(name="Máy chủ", value=str(len(self.bot.guilds)), inline=True)
        
        total_members = sum(guild.member_count for guild in self.bot.guilds)
        embed.add_field(name="Người dùng", value=str(total_members), inline=True)
        
        # Bot avatar
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        # Add footer
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", 
                         icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    def format_uptime(self, seconds: float) -> str:
        """Format seconds into a readable uptime string."""
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 or not parts:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
            
        return ", ".join(parts)
    
    @commands.hybrid_command(name="serverinfo", description="Hiển thị thông tin về server hiện tại")
    async def serverinfo(self, ctx: commands.Context):
        """Display information about the current server."""
        guild = ctx.guild
        
        # Get additional server info
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        role_count = len(guild.roles)
        emoji_count = len(guild.emojis)
        
        # Create embed
        embed = discord.Embed(
            title=f"ℹ️ Thông tin server: {guild.name}",
            color=Colors.INFO,
            description=guild.description or "Không có mô tả"
        )
        
        # Server information
        created_at = int(guild.created_at.timestamp())
        embed.add_field(name="ID", value=str(guild.id), inline=True)
        embed.add_field(name="Chủ sở hữu", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Ngày tạo", value=f"<t:{created_at}:R>", inline=True)
        
        # Member information
        member_count = guild.member_count
        online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
        bot_count = sum(1 for member in guild.members if member.bot)
        
        embed.add_field(name="Thành viên", value=f"{member_count} ({online_members} online)", inline=True)
        embed.add_field(name="Bots", value=str(bot_count), inline=True)
        embed.add_field(name="Boost Tier", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        
        # Channel information
        embed.add_field(name="Kênh", value=f"{text_channels} text, {voice_channels} voice, {categories} categories", inline=True)
        embed.add_field(name="Roles", value=str(role_count), inline=True)
        embed.add_field(name="Emojis", value=f"{emoji_count}/{guild.emoji_limit}", inline=True)
        
        # Features
        if guild.features:
            features_str = ", ".join(f"`{feature.replace('_', ' ').title()}`" for feature in guild.features)
            embed.add_field(name="Features", value=features_str, inline=False)
        
        # Server icon
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Server banner
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="userinfo", description="Hiển thị thông tin về người dùng")
    @app_commands.describe(user="Người dùng cần xem thông tin")
    async def userinfo(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Display information about a user."""
        # If no user specified, use the command author
        user = user or ctx.author
        
        # Create embed
        embed = discord.Embed(
            title=f"👤 Thông tin người dùng: {user.display_name}",
            color=user.color if user.color != discord.Color.default() else Colors.INFO
        )
        
        # User information
        embed.add_field(name="ID", value=str(user.id), inline=True)
        
        created_at = int(user.created_at.timestamp())
        embed.add_field(name="Tài khoản tạo", value=f"<t:{created_at}:R>", inline=True)
        
        joined_at = int(user.joined_at.timestamp()) if user.joined_at else None
        embed.add_field(name="Tham gia server", value=f"<t:{joined_at}:R>" if joined_at else "N/A", inline=True)
        
        # Status and activity
        status_emojis = {
            discord.Status.online: "🟢",
            discord.Status.idle: "🟡",
            discord.Status.dnd: "🔴",
            discord.Status.offline: "⚫"
        }
        
        status = f"{status_emojis.get(user.status, '⚪')} {str(user.status).title()}"
        embed.add_field(name="Trạng thái", value=status, inline=True)
        
        # Get the user's top role
        top_role = user.top_role
        if top_role != ctx.guild.default_role:
            embed.add_field(name="Role cao nhất", value=top_role.mention, inline=True)
        
        # Check if user is bot
        embed.add_field(name="Bot", value="Có" if user.bot else "Không", inline=True)
        
        # Get user activities
        if user.activities:
            activities = []
            for activity in user.activities:
                if isinstance(activity, discord.Game):
                    activities.append(f"Đang chơi: {activity.name}")
                elif isinstance(activity, discord.Streaming):
                    activities.append(f"Đang stream: {activity.name}")
                elif isinstance(activity, discord.Spotify):
                    activities.append(f"Đang nghe Spotify: {activity.title} - {activity.artist}")
                elif isinstance(activity, discord.CustomActivity):
                    if activity.emoji:
                        activities.append(f"{activity.emoji} {activity.name}")
                    else:
                        activities.append(f"{activity.name}")
                elif activity.type == discord.ActivityType.watching:
                    activities.append(f"Đang xem: {activity.name}")
                elif activity.type == discord.ActivityType.listening:
                    activities.append(f"Đang nghe: {activity.name}")
                else:
                    activities.append(f"{activity.name}")
            
            if activities:
                embed.add_field(name="Hoạt động", value="\n".join(activities), inline=False)
        
        # User avatar
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Add footer
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", 
                         icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))
