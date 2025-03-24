import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional

class Sync(commands.Cog):
    """Commands for managing bot synchronization and settings."""
    
    def __init__(self, bot):
        self.bot = bot
        self.success_color = 0xBEBEFE
        self.error_color = 0xE02B2B
        self.warning_color = 0xFFA500

    @commands.hybrid_command(
        name="sync", 
        description="Đồng bộ lại các lệnh slash."
    )
    @app_commands.describe(
        scope="Phạm vi của đồng bộ hóa: global, guild, hoặc current",
        guild_id="ID của guild để đồng bộ (khi scope là 'guild')"
    )
    @commands.is_owner()
    async def sync(
        self, 
        ctx: commands.Context, 
        scope: Literal["global", "guild", "current"] = "current",
        guild_id: Optional[int] = None
    ) -> None:
        """Synchronize slash commands with Discord.
        
        Args:
            ctx: The command context
            scope: The scope to sync commands to ('global', 'guild', or 'current')
            guild_id: Optional guild ID when scope is 'guild'
        """
        # Gửi thông báo đang xử lý
        processing_msg = await ctx.send(embed=discord.Embed(
            description="⏳ Đang đồng bộ lệnh...",
            color=self.warning_color
        ))
        
        try:
            if scope == "global":
                # Đồng bộ toàn cầu
                self.bot.tree.clear_commands(guild=None)
                await self.bot.tree.sync()
                description = "✅ Các lệnh slash đã được đồng bộ lại toàn cầu."
                
            elif scope == "guild" and guild_id:
                # Đồng bộ guild cụ thể
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    description = f"❌ Không tìm thấy guild với ID {guild_id}."
                    await processing_msg.edit(embed=discord.Embed(description=description, color=self.error_color))
                    return
                    
                self.bot.tree.clear_commands(guild=guild)
                await self.bot.tree.sync(guild=guild)
                self.bot.tree.copy_global_to(guild=guild)
                await self.bot.tree.sync(guild=guild)
                description = f"✅ Các lệnh slash đã được đồng bộ lại cho guild '{guild.name}'."
                
            elif scope == "current" or (scope == "guild" and not guild_id):
                # Đồng bộ guild hiện tại
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                self.bot.tree.copy_global_to(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                description = "✅ Các lệnh slash đã được đồng bộ lại cho guild này."
                
            else:
                description = "❌ Phạm vi không hợp lệ. Sử dụng 'global', 'guild', hoặc 'current'."
                await processing_msg.edit(embed=discord.Embed(description=description, color=self.error_color))
                return

            await processing_msg.edit(embed=discord.Embed(description=description, color=self.success_color))
            self.bot.logger.info(f"Sync hoàn thành: {description}")
                
        except Exception as e:
            error_msg = f"❌ Đã xảy ra lỗi khi đồng bộ: {str(e)}"
            await processing_msg.edit(embed=discord.Embed(description=error_msg, color=self.error_color))
            self.bot.logger.error(f"Sync error: {str(e)}")
    
    @commands.hybrid_command(
        name="unsync", 
        description="Hủy đồng bộ các lệnh slash."
    )
    @app_commands.describe(
        scope="Phạm vi của hủy đồng bộ: global, guild, hoặc current",
        guild_id="ID của guild để hủy đồng bộ (khi scope là 'guild')"
    )
    @commands.is_owner()
    async def unsync(
        self, 
        ctx: commands.Context, 
        scope: Literal["global", "guild", "current"] = "current",
        guild_id: Optional[int] = None
    ) -> None:
        """Unsynchronize slash commands from Discord.
        
        Args:
            ctx: The command context
            scope: The scope to unsync commands from ('global', 'guild', or 'current')
            guild_id: Optional guild ID when scope is 'guild'
        """
        # Gửi thông báo đang xử lý
        processing_msg = await ctx.send(embed=discord.Embed(
            description="⏳ Đang hủy đồng bộ lệnh...",
            color=self.warning_color
        ))
        
        try:
            if scope == "global":
                self.bot.tree.clear_commands(guild=None)
                await self.bot.tree.sync()
                description = "✅ Đã hủy đồng bộ các lệnh slash toàn cầu."
                
            elif scope == "guild" and guild_id:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    description = f"❌ Không tìm thấy guild với ID {guild_id}."
                    await processing_msg.edit(embed=discord.Embed(description=description, color=self.error_color))
                    return
                    
                self.bot.tree.clear_commands(guild=guild)
                await self.bot.tree.sync(guild=guild)
                description = f"✅ Đã hủy đồng bộ các lệnh slash cho guild '{guild.name}'."
                
            elif scope == "current" or (scope == "guild" and not guild_id):
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                description = "✅ Đã hủy đồng bộ các lệnh slash cho guild này."
                
            else:
                description = "❌ Phạm vi không hợp lệ. Sử dụng 'global', 'guild', hoặc 'current'."
                await processing_msg.edit(embed=discord.Embed(description=description, color=self.error_color))
                return

            await processing_msg.edit(embed=discord.Embed(description=description, color=self.success_color))
            self.bot.logger.info(f"Unsync hoàn thành: {description}")
                
        except Exception as e:
            error_msg = f"❌ Đã xảy ra lỗi khi hủy đồng bộ: {str(e)}"
            await processing_msg.edit(embed=discord.Embed(description=error_msg, color=self.error_color))
            self.bot.logger.error(f"Unsync error: {str(e)}")
    
    @commands.hybrid_command(name="setp", description="Đặt prefix cho server")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True)
    @app_commands.describe(prefix="Prefix mới cho server")
    async def setp(self, ctx: commands.Context, prefix: str) -> None:
        """Sets a new command prefix for the current guild."""
        
        # Kiểm tra độ dài prefix
        if len(prefix) > 5:
            await ctx.send(embed=discord.Embed(
                description="❌ Prefix không được dài quá 5 ký tự.", 
                color=self.error_color
            ))
            return

        guild_id = ctx.guild.id
        old_prefix = "?"  # Mặc định

        try:
            # Lấy prefix cũ để thông báo thay đổi
            self.bot.db.cursor.execute(
                "SELECT prefix FROM guilds WHERE guild_id = ?",
                (guild_id,)
            )
            result = self.bot.db.cursor.fetchone()
            if result:
                old_prefix = result[0]

            # Cập nhật hoặc thêm mới prefix vào database
            self.bot.db.cursor.execute(
                "INSERT OR REPLACE INTO guilds (guild_id, prefix) VALUES (?, ?)",
                (guild_id, prefix)
            )
            self.bot.db.conn.commit()
            
            # Thông báo thành công
            await ctx.send(embed=discord.Embed(
                description=f"✅ Đã đổi prefix từ `{old_prefix}` thành `{prefix}`",
                color=self.success_color
            ))
            
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"❌ Đã xảy ra lỗi: {str(e)}", 
                color=self.error_color
            ))
            self.bot.logger.error(f"Set prefix error: {str(e)}")
    
    @commands.command(
        name="shut",
        description="Tắt bot"
        )
    @commands.is_owner()
    async def shut(self, ctx: commands.Context) -> None:
        """Shutdown the bot."""
        await ctx.send(embed=discord.Embed(
            description="⚠️ Đang tắt bot...",
            color=self.warning_color
        ))
        self.bot.logger.info("Bot shutdown requested by owner")
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(Sync(bot))
