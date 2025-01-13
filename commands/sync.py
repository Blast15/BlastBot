import discord
from discord import app_commands
from discord.ext import commands

class Sync(commands.Cog):
    """Cog xử lý đồng bộ hóa các lệnh slash"""
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sync", description="Đồng bộ hóa các lệnh slash.")
    @app_commands.describe(scope="Phạm vi của đồng bộ hóa. Có thể là `global` hoặc `guild`")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, scope: str) -> None:
        if scope == "global":
            await ctx.bot.tree.sync()
            description = "Các lệnh slash đã được đồng bộ hóa toàn cầu."
        elif scope == "guild":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            description = "Các lệnh slash đã được đồng bộ hóa trong guild này."
        else:
            description = "Phạm vi phải là `global` hoặc `guild`."
            color = 0xE02B2B
        embed = discord.Embed(description=description, color=color if 'color' in locals() else 0xBEBEFE)
        await ctx.send(embed=embed)

    @commands.command(name="unsync", description="Hủy đồng bộ hóa các lệnh slash.")
    @app_commands.describe(scope="Phạm vi của đồng bộ hóa. Có thể là `global`, `current_guild` hoặc `guild`")
    @commands.is_owner()
    async def unsync(self, ctx: commands.Context, scope: str) -> None:
        if scope == "global":
            ctx.bot.tree.clear_commands(guild=None)
            await ctx.bot.tree.sync()
            description = "Các lệnh slash đã được hủy đồng bộ hóa toàn cầu."
        elif scope == "guild":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            description = "Các lệnh slash đã được hủy đồng bộ hóa trong guild này."
        else:
            description = "Phạm vi phải là `global` hoặc `guild`."
            color = 0xE02B2B
        embed = discord.Embed(description=description, color=color if 'color' in locals() else 0xBEBEFE)
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="setp", description="Đặt prefix cho server")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True)
    @app_commands.describe(prefix="Prefix mới cho server")
    async def setp(self, ctx: commands.Context, prefix: str) -> None:
        """Đặt prefix mới cho server hiện tại"""
        guild_id = ctx.guild.id

        try:
            # Cập nhật hoặc thêm mới prefix vào database
            self.bot.db.cursor.execute(
                "INSERT OR REPLACE INTO guilds (guild_id, prefix) VALUES (?, ?)",
                (guild_id, prefix)
            )
            self.bot.db.conn.commit()
        except Exception as e:
            await ctx.send(f"Đã xảy ra lỗi: {e}")
            return

        await ctx.send(f"Đã đặt prefix thành `{prefix}`")
    
    @commands.command(
        name="shut",
        description="Tắt bot"
        )
    @commands.is_owner()
    async def shut(self, ctx: commands.Context) -> None:
        """Tắt bot"""
        await ctx.send("Đang tắt bot...")
        await ctx.bot.close()

async def setup(bot):
    await bot.add_cog(Sync(bot))
