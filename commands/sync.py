import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal, Optional, Dict, Any, Generator
import contextlib

from utils.constants import Colors
from utils.embed_helpers import (
    create_success_embed, create_error_embed, 
    create_warning_embed, create_processing_embed
)

class Sync(commands.Cog):
    """Commands for managing bot synchronization and settings."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger.getChild("sync")
    
    async def _process_sync_command(
        self, 
        ctx: commands.Context, 
        action: Literal["sync", "unsync"],
        scope: Literal["global", "guild", "current"],
        guild_id: Optional[int] = None
    ) -> None:
        """Process sync or unsync command with common functionality.
        
        Args:
            ctx: Command context
            action: Action to perform ("sync" or "unsync")
            scope: Scope of the action
            guild_id: Optional guild ID when scope is "guild"
        """
        action_gerund = "đồng bộ" if action == "sync" else "hủy đồng bộ"
        processing_msg = await ctx.send(
            embed=create_processing_embed(f"⏳ Đang {action_gerund} lệnh...")
        )
        
        try:
            result = await self._handle_sync_action(ctx, action, scope, guild_id)
            
            if result["success"]:
                await processing_msg.edit(
                    embed=create_success_embed(result["message"])
                )
                self.logger.info(f"{action.capitalize()} hoàn thành: {result['message']}")
            else:
                await processing_msg.edit(
                    embed=create_error_embed(result["message"])
                )
                
        except Exception as e:
            error_msg = f"❌ Đã xảy ra lỗi khi {action_gerund}: {str(e)}"
            await processing_msg.edit(embed=create_error_embed(error_msg))
            self.logger.error(f"{action.capitalize()} error: {str(e)}")
    
    async def _handle_sync_action(
        self, 
        ctx: commands.Context,
        action: Literal["sync", "unsync"],
        scope: Literal["global", "guild", "current"],
        guild_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Handle the synchronization action logic.
        
        Args:
            ctx: Command context
            action: Action to perform ("sync" or "unsync")
            scope: Scope of the action
            guild_id: Optional guild ID when scope is "guild"
            
        Returns:
            Dict with success status and message
        """
        is_sync = action == "sync"
        
        if scope == "global":
            # Global sync/unsync
            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync()
            
            success_msg = "✅ Các lệnh slash đã được đồng bộ lại toàn cầu." if is_sync else \
                          "✅ Đã hủy đồng bộ các lệnh slash toàn cầu."
            return {"success": True, "message": success_msg}
            
        elif scope == "guild" and guild_id:
            # Specific guild sync/unsync
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return {
                    "success": False, 
                    "message": f"❌ Không tìm thấy guild với ID {guild_id}."
                }
                
            self.bot.tree.clear_commands(guild=guild)
            
            if is_sync:
                # For sync, we also copy global commands
                await self.bot.tree.sync(guild=guild)
                self.bot.tree.copy_global_to(guild=guild)
                await self.bot.tree.sync(guild=guild)
                success_msg = f"✅ Các lệnh slash đã được đồng bộ lại cho guild '{guild.name}'."
            else:
                # For unsync, just clear and sync the empty commands
                await self.bot.tree.sync(guild=guild)
                success_msg = f"✅ Đã hủy đồng bộ các lệnh slash cho guild '{guild.name}'."
                
            return {"success": True, "message": success_msg}
            
        elif scope == "current" or (scope == "guild" and not guild_id):
            # Current guild sync/unsync
            self.bot.tree.clear_commands(guild=ctx.guild)
            
            if is_sync:
                await self.bot.tree.sync(guild=ctx.guild)
                self.bot.tree.copy_global_to(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                success_msg = "✅ Các lệnh slash đã được đồng bộ lại cho guild này."
            else:
                await self.bot.tree.sync(guild=ctx.guild)
                success_msg = "✅ Đã hủy đồng bộ các lệnh slash cho guild này."
                
            return {"success": True, "message": success_msg}
            
        else:
            return {
                "success": False,
                "message": "❌ Phạm vi không hợp lệ. Sử dụng 'global', 'guild', hoặc 'current'."
            }
    
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
        await self._process_sync_command(ctx, "sync", scope, guild_id)
    
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
        await self._process_sync_command(ctx, "unsync", scope, guild_id)
    
    @contextlib.contextmanager
    def _db_transaction(self) -> Generator[Any, None, None]:
        """Compatibility layer for database transactions.
        
        Returns a context manager that works with both the DBManager transaction
        method and standard database connections.
        """
        if hasattr(self.bot.db, 'transaction') and callable(self.bot.db.transaction):
            # Use the transaction method if available
            with self.bot.db.transaction() as db:
                yield db
        else:
            # Fallback for standard database connections
            try:
                yield self.bot.db
                if hasattr(self.bot.db, 'commit') and callable(self.bot.db.commit):
                    self.bot.db.commit()
            except Exception as e:
                if hasattr(self.bot.db, 'rollback') and callable(self.bot.db.rollback):
                    self.bot.db.rollback()
                raise e
    
    @commands.hybrid_command(name="setp", description="Đặt prefix cho server")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True)
    @app_commands.describe(prefix="Prefix mới cho server")
    async def setp(self, ctx: commands.Context, prefix: str) -> None:
        """Sets a new command prefix for the current guild.
        
        Args:
            ctx: The command context
            prefix: The new prefix to set
        """
        if not ctx.guild:
            await ctx.send(embed=create_error_embed("❌ Lệnh này chỉ có thể sử dụng trong server."))
            return
            
        if len(prefix) > 5:
            await ctx.send(embed=create_error_embed("❌ Prefix không được dài quá 5 ký tự."))
            return
        
        try:
            with self._db_transaction() as db:
                # Determine which database interface to use
                if hasattr(db, 'execute') and callable(db.execute):
                    # Check if server exists in database
                    server_exists = db.execute(
                        "SELECT 1 FROM servers WHERE server_id = ?", 
                        (ctx.guild.id,)
                    ).fetchone()
                    
                    if not server_exists:
                        # Insert new server if it doesn't exist
                        db.execute(
                            "INSERT INTO servers (server_id, name) VALUES (?, ?)",
                            (ctx.guild.id, ctx.guild.name)
                        )
                    
                    # Update prefix
                    db.execute(
                        "UPDATE servers SET prefix = ? WHERE server_id = ?",
                        (prefix, ctx.guild.id)
                    )
                elif hasattr(db, 'cursor') and hasattr(db.cursor, 'execute'):
                    # Use cursor interface
                    cursor = db.cursor
                    cursor.execute(
                        "SELECT 1 FROM servers WHERE server_id = ?", 
                        (ctx.guild.id,)
                    )
                    server_exists = cursor.fetchone()
                    
                    if not server_exists:
                        # Insert new server if it doesn't exist
                        cursor.execute(
                            "INSERT INTO servers (server_id, name) VALUES (?, ?)",
                            (ctx.guild.id, ctx.guild.name)
                        )
                    
                    # Update prefix
                    cursor.execute(
                        "UPDATE servers SET prefix = ? WHERE server_id = ?",
                        (prefix, ctx.guild.id)
                    )
                else:
                    await ctx.send(embed=create_error_embed("❌ Không thể kết nối với cơ sở dữ liệu."))
                    return
                
                # Update the bot's prefix cache if it exists
                if hasattr(self.bot, 'prefix_cache'):
                    self.bot.prefix_cache[ctx.guild.id] = prefix
            
            await ctx.send(
                embed=create_success_embed(f"✅ Prefix server đã được đổi thành `{prefix}`")
            )
            self.logger.info(f"Changed prefix for guild {ctx.guild.id} to '{prefix}'")
            
        except Exception as e:
            await ctx.send(
                embed=create_error_embed(f"❌ Đã xảy ra lỗi khi đặt prefix: {str(e)}")
            )
            self.logger.error(f"Error setting prefix: {str(e)}")
    
    @commands.command(
        name="shut",
        description="Tắt bot"
    )
    @commands.is_owner()
    async def shut(self, ctx: commands.Context) -> None:
        """Shutdown the bot.
        
        Args:
            ctx: The command context
        """
        await ctx.send(embed=create_warning_embed("⚠️ Đang tắt bot..."))
        self.logger.info("Bot shutdown requested by owner")
        
        # Ensure we complete any pending database operations
        if hasattr(self.bot, 'db') and hasattr(self.bot.db, 'close'):
            self.bot.db.close()
            
        await self.bot.close()

async def setup(bot):
    await bot.add_cog(Sync(bot))
