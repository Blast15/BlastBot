import discord
from discord.ext import commands
from discord import app_commands
import random
import math
from typing import Dict, Optional, List, Union
import asyncio
import io
import time

from utils.constants import Colors
from utils.cache import TimedCache
from utils.embed_helpers import create_success_embed, create_error_embed

class Leveling(commands.Cog):
    """A cog that implements a basic user leveling system."""
    
    def __init__(self, bot):
        self.bot = bot
        # Cache for cooldowns to prevent spam
        self.message_cooldowns: Dict[int, float] = {}
        # Cache for levels to reduce database queries
        self.level_cache = TimedCache[Dict[str, int]](max_age=300)  # 5 minute cache
        # Constants for leveling
        self.base_xp = 15  # Base XP per message
        self.random_xp_range = 10  # Random XP bonus range
        self.cooldown = 60  # Seconds between XP gains
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle XP gain from user messages."""
        # Skip if message is from a bot or not in a guild
        if message.author.bot or not message.guild:
            return
            
        # Check cooldown for this user
        user_id = message.author.id
        current_time = time.time()
        
        if user_id in self.message_cooldowns:
            time_diff = current_time - self.message_cooldowns[user_id]
            if time_diff < self.cooldown:
                return  # Still on cooldown
        
        # Update cooldown
        self.message_cooldowns[user_id] = current_time
        
        try:
            # Calculate XP gained
            xp_gain = self.base_xp + random.randint(0, self.random_xp_range)
            
            # Get current level and XP
            current_level, current_xp = await self.get_level_and_xp(message.guild.id, user_id)
            
            # Add XP
            new_xp = current_xp + xp_gain
            
            # Calculate level from XP
            new_level = self.calculate_level_from_xp(new_xp)
            
            # Update cache for faster access
            self.level_cache.set(
                f"{message.guild.id}:{user_id}", 
                {"level": new_level, "xp": new_xp}
            )
            
            # Update database
            self.bot.db.cursor.execute(
                "INSERT OR REPLACE INTO levels (guild_id, user_id, xp) VALUES (?, ?, ?)",
                (message.guild.id, user_id, new_xp)
            )
            self.bot.db.conn.commit()
            
            # Check for level up
            if new_level > current_level:
                await self.handle_level_up(message, new_level)
                
        except Exception as e:
            self.bot.logger.error(f"Error in leveling system: {str(e)}")
    
    async def handle_level_up(self, message: discord.Message, new_level: int):
        """Handle level up events including notifications and role rewards."""
        try:
            # Check if level up notifications are enabled
            self.bot.db.cursor.execute(
                "SELECT levelup_channel_id, levelup_enabled FROM guilds WHERE guild_id = ?",
                (message.guild.id,)
            )
            result = self.bot.db.cursor.fetchone()
            
            if not result:
                return
                
            levelup_channel_id, levelup_enabled = result
            
            # Only send notification if enabled
            if levelup_enabled:
                # Determine where to send notification
                if levelup_channel_id:
                    # Send to specific channel
                    channel = message.guild.get_channel(levelup_channel_id)
                    if not channel:
                        return
                else:
                    # Send to same channel as message
                    channel = message.channel
                    
                # Send level up notification
                embed = discord.Embed(
                    description=f"🎉 **{message.author.mention} đã đạt level {new_level}!**",
                    color=Colors.SUCCESS
                )
                embed.set_thumbnail(url=message.author.display_avatar.url)
                
                await channel.send(embed=embed)
                
            # Check for level roles
            self.bot.db.cursor.execute(
                "SELECT role_id FROM level_roles WHERE guild_id = ? AND level <= ? ORDER BY level DESC LIMIT 1",
                (message.guild.id, new_level)
            )
            role_result = self.bot.db.cursor.fetchone()
            
            if role_result and role_result[0]:
                role_id = role_result[0]
                role = message.guild.get_role(role_id)
                
                if role and role not in message.author.roles:
                    try:
                        await message.author.add_roles(role)
                        
                        # Notify about role gain
                        role_embed = discord.Embed(
                            description=f"✨ {message.author.mention} đã nhận được role {role.mention} từ level up!",
                            color=Colors.SUCCESS
                        )
                        
                        await channel.send(embed=role_embed)
                    except discord.Forbidden:
                        self.bot.logger.error(f"Missing permissions to add role in {message.guild.name}")
            
        except Exception as e:
            self.bot.logger.error(f"Error in level up handler: {str(e)}")
    
    async def get_level_and_xp(self, guild_id: int, user_id: int) -> tuple[int, int]:
        """Get a user's level and XP from cache or database."""
        # Check cache first
        cache_key = f"{guild_id}:{user_id}"
        cached_data = self.level_cache.get(cache_key)
        
        if cached_data:
            return cached_data["level"], cached_data["xp"]
            
        # Query database if not in cache
        self.bot.db.cursor.execute(
            "SELECT xp FROM levels WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        result = self.bot.db.cursor.fetchone()
        
        if result:
            xp = result[0]
            level = self.calculate_level_from_xp(xp)
            
            # Update cache
            self.level_cache.set(cache_key, {"level": level, "xp": xp})
            
            return level, xp
        else:
            # No data found, user has 0 XP
            return 0, 0
    
    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate user level based on XP amount."""
        # Simplified formula: level = sqrt(xp / 100)
        return int(math.sqrt(xp / 100))
    
    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate required XP for a specific level."""
        return int(level * level * 100)
    
    @commands.hybrid_command(name="rank", description="Hiển thị cấp độ của bạn hoặc người dùng khác")
    @commands.cooldown(1, 10, commands.BucketType.user)
    @app_commands.describe(user="Người dùng cần xem cấp độ")
    async def rank(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Display level and XP for a user."""
        if not user:
            user = ctx.author
            
        # Get level and XP
        level, xp = await self.get_level_and_xp(ctx.guild.id, user.id)
        
        # Calculate progress to next level
        current_level_xp = self.calculate_xp_for_level(level)
        next_level_xp = self.calculate_xp_for_level(level + 1)
        xp_needed = next_level_xp - current_level_xp
        xp_progress = xp - current_level_xp
        xp_percent = min(int((xp_progress / xp_needed) * 100), 100) if xp_needed > 0 else 100
        
        # Create progress bar
        progress_bar = self.create_progress_bar(xp_percent)
        
        embed = discord.Embed(
            title=f"Cấp độ của {user.display_name}",
            color=Colors.INFO
        )
        
        embed.add_field(
            name=f"Level {level} | XP: {xp}",
            value=f"{progress_bar} {xp_percent}%\n"
                  f"{xp_progress}/{xp_needed} XP đến level {level+1}",
            inline=False
        )
        
        # Get rank position
        self.bot.db.cursor.execute(
            "SELECT COUNT(*) FROM levels WHERE guild_id = ? AND xp > (SELECT xp FROM levels WHERE guild_id = ? AND user_id = ?)",
            (ctx.guild.id, ctx.guild.id, user.id)
        )
        rank_result = self.bot.db.cursor.fetchone()
        rank = rank_result[0] + 1 if rank_result else "N/A"
        
        embed.add_field(name="Hạng", value=f"#{rank}", inline=True)
        
        # Set user avatar
        embed.set_thumbnail(url=user.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    def create_progress_bar(self, percent: int, length: int = 10) -> str:
        """Create a text-based progress bar."""
        filled_len = int(length * percent / 100)
        bar = '▰' * filled_len + '▱' * (length - filled_len)
        return bar
    
    @commands.hybrid_command(name="leaderboard", aliases=["lb"], description="Hiển thị bảng xếp hạng cấp độ")
    @commands.cooldown(1, 30, commands.BucketType.guild)
    @app_commands.describe(page="Trang của bảng xếp hạng")
    async def leaderboard(self, ctx: commands.Context, page: Optional[int] = 1):
        """Display the server's level leaderboard."""
        if page < 1:
            await ctx.send(embed=create_error_embed("❌ Số trang phải lớn hơn 0"))
            return
            
        # Items per page
        per_page = 10
        
        # Get total count for pagination
        self.bot.db.cursor.execute(
            "SELECT COUNT(*) FROM levels WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        total_users = self.bot.db.cursor.fetchone()[0]
        
        if total_users == 0:
            await ctx.send(embed=create_error_embed("❌ Chưa có dữ liệu cấp độ nào cho server này!"))
            return
            
        max_pages = math.ceil(total_users / per_page)
        if page > max_pages:
            page = max_pages
            
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get leaderboard data
        self.bot.db.cursor.execute(
            "SELECT user_id, xp FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT ? OFFSET ?",
            (ctx.guild.id, per_page, offset)
        )
        leaderboard_data = self.bot.db.cursor.fetchall()
        
        embed = discord.Embed(
            title=f"🏆 Bảng xếp hạng cấp độ - {ctx.guild.name}",
            color=Colors.INFO
        )
        
        # Add leaderboard entries
        for i, (user_id, xp) in enumerate(leaderboard_data, start=offset+1):
            # Try to get member from guild
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"Người dùng #{user_id}"
            
            level = self.calculate_level_from_xp(xp)
            
            # Medal emojis for top 3
            medal = ""
            if i == 1:
                medal = "🥇 "
            elif i == 2:
                medal = "🥈 "
            elif i == 3:
                medal = "🥉 "
                
            embed.add_field(
                name=f"{medal}#{i}: {name}",
                value=f"Level {level} | XP: {xp}",
                inline=False
            )
        
        embed.set_footer(text=f"Trang {page}/{max_pages} • {total_users} người dùng")
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_group(name="levelrole", description="Quản lý role theo cấp độ")
    @commands.has_permissions(manage_roles=True)
    async def levelrole_group(self, ctx: commands.Context):
        """Commands for managing level roles."""
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=create_error_embed(
                "Vui lòng sử dụng lệnh con: `add`, `remove`, `list`"))
    
    @levelrole_group.command(name="add", description="Thêm role thưởng khi đạt cấp độ")
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(level="Cấp độ cần đạt được", role="Role sẽ được thưởng")
    async def add_level_role(self, ctx: commands.Context, level: int, role: discord.Role):
        """Add a role reward for reaching a specific level."""
        if level < 1:
            await ctx.send(embed=create_error_embed("❌ Cấp độ phải lớn hơn 0"))
            return
            
        # Check if bot can manage this role
        if ctx.guild.me.top_role <= role:
            await ctx.send(embed=create_error_embed(
                "❌ Role này cao hơn hoặc bằng role cao nhất của bot. Không thể tự động gán!"
            ))
            return
            
        try:
            # Check if this level already has a role
            self.bot.db.cursor.execute(
                "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                (ctx.guild.id, level)
            )
            existing_role = self.bot.db.cursor.fetchone()
            
            if existing_role:
                # Update existing record
                self.bot.db.cursor.execute(
                    "UPDATE level_roles SET role_id = ? WHERE guild_id = ? AND level = ?",
                    (role.id, ctx.guild.id, level)
                )
            else:
                # Insert new record
                self.bot.db.cursor.execute(
                    "INSERT INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                    (ctx.guild.id, level, role.id)
                )
                
            self.bot.db.conn.commit()
            
            await ctx.send(embed=create_success_embed(
                f"✅ Đã thiết lập {role.mention} làm phần thưởng cho level {level}!"
            ))
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error adding level role: {str(e)}")
    
    @levelrole_group.command(name="remove", description="Xóa role thưởng cho cấp độ")
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(level="Cấp độ cần xóa phần thưởng")
    async def remove_level_role(self, ctx: commands.Context, level: int):
        """Remove a role reward for a specific level."""
        try:
            # Check if this level has a role
            self.bot.db.cursor.execute(
                "SELECT role_id FROM level_roles WHERE guild_id = ? AND level = ?",
                (ctx.guild.id, level)
            )
            existing_role = self.bot.db.cursor.fetchone()
            
            if not existing_role:
                await ctx.send(embed=create_error_embed(
                    f"❌ Không tìm thấy role thưởng nào cho level {level}!"
                ))
                return
                
            # Get role for better feedback
            role_id = existing_role[0]
            role = ctx.guild.get_role(role_id)
            role_name = role.name if role else f"ID: {role_id}"
                
            # Delete record
            self.bot.db.cursor.execute(
                "DELETE FROM level_roles WHERE guild_id = ? AND level = ?",
                (ctx.guild.id, level)
            )
            self.bot.db.conn.commit()
            
            await ctx.send(embed=create_success_embed(
                f"✅ Đã xóa role thưởng {role_name} cho level {level}!"
            ))
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error removing level role: {str(e)}")
    
    @levelrole_group.command(name="list", description="Liệt kê tất cả role thưởng theo cấp độ")
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def list_level_roles(self, ctx: commands.Context):
        """List all level role rewards for the current server."""
        try:
            self.bot.db.cursor.execute(
                "SELECT level, role_id FROM level_roles WHERE guild_id = ? ORDER BY level ASC",
                (ctx.guild.id,)
            )
            level_roles = self.bot.db.cursor.fetchall()
            
            if not level_roles:
                await ctx.send(embed=create_error_embed(
                    "❌ Chưa có role thưởng nào được thiết lập cho server này!"
                ))
                return
                
            embed = discord.Embed(
                title="🏅 Danh sách Role Thưởng",
                description="Các role sẽ được tự động gán khi đạt cấp độ tương ứng:",
                color=Colors.INFO
            )
            
            for level, role_id in level_roles:
                role = ctx.guild.get_role(role_id)
                if role:
                    embed.add_field(
                        name=f"Level {level}",
                        value=role.mention,
                        inline=True
                    )
                else:
                    embed.add_field(
                        name=f"Level {level}",
                        value=f"Role không tồn tại (ID: {role_id})",
                        inline=True
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error listing level roles: {str(e)}")
    
    @commands.hybrid_group(name="levelconfig", description="Cấu hình hệ thống cấp độ")
    @commands.has_permissions(manage_guild=True)
    async def levelconfig_group(self, ctx: commands.Context):
        """Configure level system settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=create_error_embed(
                "Vui lòng sử dụng lệnh con: `channel`, `toggle`, `multiplier`"))
    
    @levelconfig_group.command(name="channel", description="Đặt kênh thông báo level up")
    @commands.has_permissions(manage_guild=True)
    async def set_levelup_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set the channel for level up notifications."""
        try:
            # Check if guild exists in DB first
            self.bot.db.cursor.execute(
                "SELECT COUNT(*) FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            
            if self.bot.db.cursor.fetchone()[0] == 0:
                # Insert new guild with levelup channel
                self.bot.db.cursor.execute(
                    "INSERT INTO guilds (guild_id, levelup_channel_id, levelup_enabled) VALUES (?, ?, ?)",
                    (ctx.guild.id, channel.id if channel else None, True)
                )
            else:
                # Update existing guild
                self.bot.db.cursor.execute(
                    "UPDATE guilds SET levelup_channel_id = ?, levelup_enabled = ? WHERE guild_id = ?",
                    (channel.id if channel else None, True, ctx.guild.id)
                )
                
            self.bot.db.conn.commit()
            
            if channel:
                await ctx.send(embed=create_success_embed(
                    f"✅ Đã đặt {channel.mention} làm kênh thông báo level up!"
                ))
            else:
                await ctx.send(embed=create_success_embed(
                    "✅ Thông báo level up sẽ được gửi vào kênh nơi người dùng chat!"
                ))
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error setting levelup channel: {str(e)}")
    
    @levelconfig_group.command(name="toggle", description="Bật/tắt thông báo level up")
    @commands.has_permissions(manage_guild=True)
    async def toggle_levelup(self, ctx: commands.Context):
        """Toggle level up notifications on or off."""
        try:
            # Check current status
            self.bot.db.cursor.execute(
                "SELECT levelup_enabled FROM guilds WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            result = self.bot.db.cursor.fetchone()
            
            if not result:
                # Insert new guild with levelup toggled on
                self.bot.db.cursor.execute(
                    "INSERT INTO guilds (guild_id, levelup_enabled) VALUES (?, ?)",
                    (ctx.guild.id, True)
                )
                new_state = True
            else:
                new_state = not result[0]
                # Update existing guild
                self.bot.db.cursor.execute(
                    "UPDATE guilds SET levelup_enabled = ? WHERE guild_id = ?",
                    (new_state, ctx.guild.id)
                )
                
            self.bot.db.conn.commit()
            
            status = "bật" if new_state else "tắt"
            await ctx.send(embed=create_success_embed(
                f"✅ Đã {status} thông báo level up!"
            ))
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error toggling levelup: {str(e)}")
    
    @levelconfig_group.command(name="reset", description="Xóa tất cả dữ liệu cấp độ trong server")
    @commands.has_permissions(administrator=True)
    async def reset_levels(self, ctx: commands.Context):
        """Reset all levels and XP for the current server."""
        try:
            view = ConfirmView()
            message = await ctx.send(
                embed=discord.Embed(
                    title="⚠️ Xác nhận xóa",
                    description="Bạn có chắc muốn xóa **TẤT CẢ** dữ liệu cấp độ trong server này?\n"
                                "Hành động này không thể hoàn tác!",
                    color=Colors.WARNING
                ),
                view=view
            )
            
            # Wait for confirmation
            await view.wait()
            
            if view.value is True:
                # Delete all level data for this guild
                self.bot.db.cursor.execute(
                    "DELETE FROM levels WHERE guild_id = ?",
                    (ctx.guild.id,)
                )
                self.bot.db.conn.commit()
                
                # Clear cache entries for this guild
                for key in list(self.level_cache.cache.keys()):
                    if key.startswith(f"{ctx.guild.id}:"):
                        self.level_cache.delete(key)
                
                await message.edit(
                    embed=create_success_embed("✅ Đã xóa tất cả dữ liệu cấp độ trong server này!"),
                    view=None
                )
            else:
                await message.edit(
                    embed=discord.Embed(
                        description="❌ Đã hủy xóa dữ liệu cấp độ.",
                        color=Colors.ERROR
                    ),
                    view=None
                )
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error resetting levels: {str(e)}")

class ConfirmView(discord.ui.View):
    """Confirmation view with Yes/No buttons."""
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None
    
    @discord.ui.button(label="Có", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.defer()
        self.stop()
    
    @discord.ui.button(label="Không", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()
    
    async def on_timeout(self):
        """Handle view timeout."""
        self.value = False
        self.stop()

async def setup(bot):
    # Create the table if it doesn't exist
    bot.db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS levels (
            guild_id INTEGER,
            user_id INTEGER,
            xp INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')
    
    bot.db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS level_roles (
            guild_id INTEGER,
            level INTEGER,
            role_id INTEGER,
            PRIMARY KEY (guild_id, level)
        )
    ''')
    
    # Add columns to guilds table if they don't exist
    # This requires checking if columns exist first because SQLite doesn't support IF NOT EXISTS for columns
    try:
        bot.db.cursor.execute('SELECT levelup_channel_id FROM guilds LIMIT 1')
    except:
        bot.db.cursor.execute('ALTER TABLE guilds ADD COLUMN levelup_channel_id INTEGER')
    
    try:
        bot.db.cursor.execute('SELECT levelup_enabled FROM guilds LIMIT 1')
    except:
        bot.db.cursor.execute('ALTER TABLE guilds ADD COLUMN levelup_enabled BOOLEAN DEFAULT 0')
    
    bot.db.conn.commit()
    
    await bot.add_cog(Leveling(bot))
