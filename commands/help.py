import discord
from discord.ext import commands
from typing import Optional

class Help(commands.Cog):
    """A cog that provides help command functionality for the bot.
    This cog implements a help command that displays either a general overview of all available commands
    grouped by their cogs, or detailed information about a specific command when requested.
    Attributes:
        bot: The bot instance that loaded this cog.
    Methods:
        help(ctx, command): Shows help information about commands.
            - If no command is specified, displays an overview of all commands grouped by cogs
            - If a command name is provided, shows detailed information about that specific command
    """
    
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Hiển thị trợ giúp về các lệnh")
    async def help(self, ctx: commands.Context, command: Optional[str] = None) -> None:
        """Help command to display available commands and their usage.
        This command provides two functionalities:
        1. Without parameters: Shows an overview of all available commands grouped by cogs
        2. With command parameter: Shows detailed help for a specific command
            ctx (commands.Context): The invocation context
            command (Optional[str]): The name of command to get detailed help for. Defaults to None.
        Returns:
            None
        Example usage:
            !help
            !help play
        Notes:
            - Hidden commands are not shown in the overview
            - Empty cogs (with no commands) are skipped
            - For specific commands, shows aliases and usage if available
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
                title="Trợ giúp Blast Bot",
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
