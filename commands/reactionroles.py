import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, List, Tuple
import json

from utils.constants import Colors
from utils.embed_helpers import create_success_embed, create_error_embed, create_processing_embed

class ReactionRoles(commands.Cog):
    """A cog that handles reaction role functionality."""
    
    def __init__(self, bot):
        self.bot = bot
        # Cache reaction role data for quick lookup
        self.reaction_roles: Dict[int, Dict[int, Dict[str, int]]] = {} # {guild_id: {message_id: {emoji: role_id}}}
        self.bot.loop.create_task(self.load_reaction_roles())
    
    async def load_reaction_roles(self):
        """Load reaction roles from the database into cache."""
        await self.bot.wait_until_ready()
        
        try:
            self.bot.db.cursor.execute("SELECT guild_id, message_id, emoji_role_data FROM reaction_roles")
            rows = self.bot.db.cursor.fetchall()
            
            for guild_id, message_id, emoji_role_data in rows:
                if guild_id not in self.reaction_roles:
                    self.reaction_roles[guild_id] = {}
                    
                self.reaction_roles[guild_id][message_id] = json.loads(emoji_role_data)
            
            self.bot.logger.info(f"Loaded reaction roles for {len(self.reaction_roles)} guilds")
        except Exception as e:
            self.bot.logger.error(f"Error loading reaction roles: {str(e)}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle role assignment when a reaction is added."""
        # Skip bot reactions
        if payload.user_id == self.bot.user.id:
            return
            
        try:
            # Check if this reaction is for a role
            guild_id = payload.guild_id
            message_id = payload.message_id
            
            if not guild_id or not message_id:
                return
                
            # Check if the message has reaction roles
            if (guild_id not in self.reaction_roles or 
                message_id not in self.reaction_roles[guild_id]):
                return
                
            # Get emoji string representation
            emoji = str(payload.emoji)
            
            # Check if this emoji is configured for a role
            if emoji not in self.reaction_roles[guild_id][message_id]:
                return
                
            # Get the role ID and assign it
            role_id = self.reaction_roles[guild_id][message_id][emoji]
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                return
                
            role = guild.get_role(role_id)
            if not role:
                return
                
            member = guild.get_member(payload.user_id)
            if not member:
                return
                
            await member.add_roles(role)
            
        except Exception as e:
            self.bot.logger.error(f"Error in reaction role add: {str(e)}")
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle role removal when a reaction is removed."""
        # Skip bot reactions
        if payload.user_id == self.bot.user.id:
            return
            
        try:
            # Check if this reaction is for a role
            guild_id = payload.guild_id
            message_id = payload.message_id
            
            if not guild_id or not message_id:
                return
                
            # Check if the message has reaction roles
            if (guild_id not in self.reaction_roles or 
                message_id not in self.reaction_roles[guild_id]):
                return
                
            # Get emoji string representation
            emoji = str(payload.emoji)
            
            # Check if this emoji is configured for a role
            if emoji not in self.reaction_roles[guild_id][message_id]:
                return
                
            # Get the role ID and remove it
            role_id = self.reaction_roles[guild_id][message_id][emoji]
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                return
                
            role = guild.get_role(role_id)
            if not role:
                return
                
            member = guild.get_member(payload.user_id)
            if not member:
                return
                
            await member.remove_roles(role)
            
        except Exception as e:
            self.bot.logger.error(f"Error in reaction role remove: {str(e)}")
    
    @commands.hybrid_group(name="reactionrole", aliases=["rr"], description="Quản lý role gán bằng reaction")
    @commands.has_permissions(manage_roles=True)
    async def reactionrole_group(self, ctx: commands.Context):
        """Reaction role management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=create_error_embed(
                "Vui lòng sử dụng lệnh con: `create`, `add`, `remove`, `list`"))
    
    @reactionrole_group.command(name="create", description="Tạo một thông báo để gán role bằng reaction")
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(
        title="Tiêu đề của thông báo",
        description="Mô tả về hệ thống role"
    )
    async def create_reaction_message(self, ctx: commands.Context, title: str, *, description: str):
        """Create a new reaction role message."""
        try:
            embed = discord.Embed(
                title=title,
                description=description,
                color=Colors.INFO
            )
            embed.set_footer(text="Nhấn vào reaction để nhận role tương ứng")
            
            # Send the message
            message = await ctx.send(embed=embed)
            
            # Initialize in database and cache
            if ctx.guild.id not in self.reaction_roles:
                self.reaction_roles[ctx.guild.id] = {}
                
            self.reaction_roles[ctx.guild.id][message.id] = {}
            
            # Store in database
            emoji_role_data = json.dumps({})
            self.bot.db.cursor.execute(
                "INSERT INTO reaction_roles (guild_id, message_id, emoji_role_data) VALUES (?, ?, ?)",
                (ctx.guild.id, message.id, emoji_role_data)
            )
            self.bot.db.conn.commit()
            
            # Notify success
            await ctx.send(embed=create_success_embed(
                f"✅ Đã tạo thông báo gán role! ID: {message.id}\n" +
                "Sử dụng `reactionrole add` để thêm role vào thông báo này."
            ))
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error creating reaction role message: {str(e)}")
    
    @reactionrole_group.command(name="add", description="Thêm role vào hệ thống reaction")
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(
        message_id="ID của thông báo",
        emoji="Emoji để gán role",
        role="Role được gán"
    )
    async def add_reaction_role(self, ctx: commands.Context, message_id: str, emoji: str, role: discord.Role):
        """Add a new reaction-role pair to a message."""
        try:
            # Convert message_id to int
            try:
                message_id = int(message_id)
            except ValueError:
                await ctx.send(embed=create_error_embed("❌ ID thông báo không hợp lệ!"))
                return
                
            # Verify the message exists and is from this bot
            try:
                channel = ctx.channel
                message = await channel.fetch_message(message_id)
                
                if message.author.id != self.bot.user.id:
                    await ctx.send(embed=create_error_embed(
                        "❌ Tin nhắn này không phải do bot tạo ra!"
                    ))
                    return
            except discord.NotFound:
                await ctx.send(embed=create_error_embed(
                    "❌ Không tìm thấy tin nhắn trong kênh này!"
                ))
                return
                
            # Check if this message is in the reaction roles system
            if (ctx.guild.id not in self.reaction_roles or 
                message_id not in self.reaction_roles[ctx.guild.id]):
                await ctx.send(embed=create_error_embed(
                    "❌ Tin nhắn này chưa được thiết lập cho hệ thống reaction role!"
                ))
                return
                
            # Add the reaction to the message
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                await ctx.send(embed=create_error_embed(
                    f"❌ Không thể thêm reaction {emoji}! Emoji không hợp lệ hoặc bot không có quyền."
                ))
                return
                
            # Update cache
            self.reaction_roles[ctx.guild.id][message_id][emoji] = role.id
            
            # Update database
            emoji_role_data = json.dumps(self.reaction_roles[ctx.guild.id][message_id])
            self.bot.db.cursor.execute(
                "UPDATE reaction_roles SET emoji_role_data = ? WHERE guild_id = ? AND message_id = ?",
                (emoji_role_data, ctx.guild.id, message_id)
            )
            self.bot.db.conn.commit()
            
            # Notify success
            await ctx.send(embed=create_success_embed(
                f"✅ Đã thêm {emoji} -> {role.mention} vào hệ thống reaction role!"
            ))
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error adding reaction role: {str(e)}")
    
    @reactionrole_group.command(name="remove", description="Xóa role khỏi hệ thống reaction")
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(
        message_id="ID của thông báo",
        emoji="Emoji cần xóa"
    )
    async def remove_reaction_role(self, ctx: commands.Context, message_id: str, emoji: str):
        """Remove a reaction-role pair from a message."""
        try:
            # Convert message_id to int
            try:
                message_id = int(message_id)
            except ValueError:
                await ctx.send(embed=create_error_embed("❌ ID thông báo không hợp lệ!"))
                return
                
            # Verify the message exists in our system
            if (ctx.guild.id not in self.reaction_roles or 
                message_id not in self.reaction_roles[ctx.guild.id] or
                emoji not in self.reaction_roles[ctx.guild.id][message_id]):
                await ctx.send(embed=create_error_embed(
                    f"❌ Không tìm thấy role với emoji {emoji} trong thông báo này!"
                ))
                return
                
            # Remove the reaction from the message
            try:
                channel = ctx.channel
                message = await channel.fetch_message(message_id)
                await message.clear_reaction(emoji)
            except discord.NotFound:
                pass  # Message may have been deleted, continue with DB cleanup
                
            # Update cache
            role_id = self.reaction_roles[ctx.guild.id][message_id][emoji]
            del self.reaction_roles[ctx.guild.id][message_id][emoji]
            
            # Update database
            emoji_role_data = json.dumps(self.reaction_roles[ctx.guild.id][message_id])
            self.bot.db.cursor.execute(
                "UPDATE reaction_roles SET emoji_role_data = ? WHERE guild_id = ? AND message_id = ?",
                (emoji_role_data, ctx.guild.id, message_id)
            )
            self.bot.db.conn.commit()
            
            # Get role name for better feedback
            role = ctx.guild.get_role(role_id)
            role_name = role.name if role else f"ID: {role_id}"
            
            # Notify success
            await ctx.send(embed=create_success_embed(
                f"✅ Đã xóa {emoji} -> {role_name} khỏi hệ thống reaction role!"
            ))
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error removing reaction role: {str(e)}")
    
    @reactionrole_group.command(name="list", description="Liệt kê tất cả role gán bằng reaction")
    @commands.has_permissions(manage_roles=True)
    async def list_reaction_roles(self, ctx: commands.Context):
        """List all reaction roles for the current server."""
        try:
            if (ctx.guild.id not in self.reaction_roles or 
                not self.reaction_roles[ctx.guild.id]):
                await ctx.send(embed=create_error_embed(
                    "❌ Chưa có reaction role nào được thiết lập cho server này!"
                ))
                return
                
            embed = discord.Embed(
                title="📋 Danh sách Reaction Roles",
                color=Colors.INFO
            )
            
            for message_id, emoji_roles in self.reaction_roles[ctx.guild.id].items():
                if not emoji_roles:
                    continue
                    
                value = ""
                for emoji, role_id in emoji_roles.items():
                    role = ctx.guild.get_role(role_id)
                    role_mention = role.mention if role else f"Role không tồn tại (ID: {role_id})"
                    value += f"{emoji} -> {role_mention}\n"
                
                if value:
                    embed.add_field(
                        name=f"Tin nhắn ID: {message_id}",
                        value=value,
                        inline=False
                    )
            
            if len(embed.fields) == 0:
                await ctx.send(embed=create_error_embed(
                    "❌ Chưa có reaction role nào được thiết lập cho server này!"
                ))
                return
                
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(embed=create_error_embed(f"❌ Lỗi: {str(e)}"))
            self.bot.logger.error(f"Error listing reaction roles: {str(e)}")

async def setup(bot):
    # Create the table if it doesn't exist
    bot.db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS reaction_roles (
            guild_id INTEGER,
            message_id INTEGER,
            emoji_role_data TEXT,
            PRIMARY KEY (guild_id, message_id)
        )
    ''')
    bot.db.conn.commit()
    
    await bot.add_cog(ReactionRoles(bot))
