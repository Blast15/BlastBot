import discord
from discord.ext import commands
import traceback

class ErrorHandler(commands.Cog):
    """Xử lý các lỗi xảy ra khi thực thi lệnh"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """
        Xử lý lỗi từ các lệnh
        Parameters:
            ctx (Context): Context của lệnh
            error (Exception): Lỗi xảy ra
        """
        if isinstance(error, commands.CommandNotFound):
            return  # Bỏ qua lỗi lệnh không tồn tại
            
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(f"❌ Bạn cần quyền {perms} để thực hiện lệnh này!")
            return
            
        if isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions)
            await ctx.send(f"❌ Bot cần quyền {perms} để thực hiện lệnh này!")
            return
            
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Thiếu tham số: {error.param.name}")
            return
            
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Vui lòng đợi {error.retry_after:.1f}s để dùng lại lệnh này!")
            return
        
        if isinstance(error, commands.DisabledCommand):
            await ctx.send("❌ Lệnh này đã bị vô hiệu hóa")
            return
            
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ Lệnh này chỉ có thể dùng trong server")
            return

        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Chỉ chủ bot mới dùng được lệnh này")
            return

        # Log lỗi không xác định
        self.bot.logger.error(f"Lỗi trong lệnh {ctx.command}:")
        self.bot.logger.error(f"".join(traceback.format_exception(type(error), error, error.__traceback__)))

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
