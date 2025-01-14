import discord
from discord.ext import commands
from typing import Optional

class Help(commands.Cog):
    """Hiển thị trợ giúp về các lệnh của bot"""
    
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Hiển thị trợ giúp về các lệnh")
    async def help(self, ctx: commands.Context, command: Optional[str] = None) -> None:
        """
        Hiển thị trợ giúp về các lệnh
        Parameters:
            command (str): Tên lệnh cần xem trợ giúp chi tiết
        """
        if command:
            # Hiển thị trợ giúp chi tiết cho một lệnh cụ thể
            cmd = self.bot.get_command(command)
            if not cmd:
                await ctx.send("❌ Không tìm thấy lệnh này!")
                return

            embed = discord.Embed(
                title=f"Trợ giúp: {cmd.name}",
                description=cmd.description or "Không có mô tả",
                color=0x2F3136
            )

            if cmd.aliases:
                embed.add_field(name="Tên khác", value=", ".join(cmd.aliases), inline=False)
            
            usage = f"{ctx.prefix}{cmd.qualified_name}"
            if cmd.signature:
                usage += f" {cmd.signature}"
            embed.add_field(name="Cách dùng", value=f"```{usage}```", inline=False)

        else:
            # Hiển thị tổng quan các lệnh
            embed = discord.Embed(
                title="Trợ giúp Bot Discord",
                description="Danh sách các lệnh có sẵn:",
                color=0x2F3136
            )

            for cog_name, cog in self.bot.cogs.items():
                if not cog.get_commands():  # Bỏ qua cog không có lệnh
                    continue
                    
                commands_list = []
                for cmd in cog.get_commands():
                    if cmd.hidden:  # Bỏ qua lệnh ẩn
                        continue
                    commands_list.append(f"`{cmd.name}`: {cmd.description}")

                if commands_list:  # Chỉ thêm cog có lệnh hiển thị
                    embed.add_field(
                        name=cog_name,
                        value="\n".join(commands_list),
                        inline=False
                    )

        embed.set_footer(text=f"Gõ {ctx.prefix}help <lệnh> để xem chi tiết về một lệnh cụ thể")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
