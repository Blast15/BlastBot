import discord
from discord import app_commands
from discord.ext import commands

class Sync(commands.Cog):
    """A Cog containing commands for managing bot synchronization and settings.
    This cog provides commands to synchronize slash commands globally or per guild,
    set custom prefixes for servers, and shutdown the bot. These commands are
    primarily intended for bot administrators and owners.
    Attributes:
        bot: The bot instance that the cog is attached to
    Commands:
        sync: Synchronizes slash commands either globally or for a specific guild
        setp: Sets a custom command prefix for the current server
        shut: Shuts down the bot
    Requirements:
        - Bot must have appropriate permissions to manage slash commands
        - Database connection for prefix management
    """
    
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sync", description="Đồng bộ lại các lệnh slash.")
    @app_commands.describe(
        scope="Phạm vi của đồng bộ hóa. Có thể là `global` hoặc `guild`"
    )
    @commands.is_owner()
    async def sync(self, ctx: commands.Context, scope: str) -> None:
        """Synchronize slash commands with Discord, either globally or for a specific guild.
        This coroutine syncs application commands by first clearing them and then re-syncing,
        either globally across all guilds or for a specific guild only.
        Parameters
        ----------
        ctx : commands.Context
            The invocation context containing information about where/who invoked command
        scope : str
            The scope to sync commands to - must be either "global" or "guild"
            - "global": Syncs commands across all guilds the bot is in
            - "guild": Syncs commands only for the guild where command was invoked
        Returns
        -------
        None
            Sends an embed message indicating success or failure of the sync operation
        Raises
        ------
        Exception
            If there is an error during the sync process, it will be caught and reported in the embed
        """
        if scope not in ["global", "guild"]:
            embed = discord.Embed(
                description="Phạm vi phải là `global` hoặc `guild`.",
                color=0xE02B2B
            )
        else:
            try:
                if scope == "global":
                    # Unsync
                    ctx.bot.tree.clear_commands(guild=None)
                    await ctx.bot.tree.sync()
                    # Sync
                    await ctx.bot.tree.sync()
                    description = "Các lệnh slash đã được đồng bộ lại toàn cầu."
                else:  # guild
                    # Unsync
                    ctx.bot.tree.clear_commands(guild=ctx.guild)
                    await ctx.bot.tree.sync(guild=ctx.guild)
                    # Sync
                    ctx.bot.tree.copy_global_to(guild=ctx.guild)
                    await ctx.bot.tree.sync(guild=ctx.guild)
                    description = "Các lệnh slash đã được đồng bộ lại trong guild này."

                embed = discord.Embed(description=description, color=0xBEBEFE)
            except Exception as e:
                embed = discord.Embed(
                    description=f"Đã xảy ra lỗi: {str(e)}",
                    color=0xE02B2B
                )
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="setp", description="Đặt prefix cho server")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True)
    @app_commands.describe(prefix="Prefix mới cho server")
    async def setp(self, ctx: commands.Context, prefix: str) -> None:
        """Sets a new command prefix for the current guild.
        This method updates or inserts a new command prefix for the guild in the database.
        If an error occurs during the database operation, it will be caught and reported
        to the user.
        Args:
            ctx (commands.Context): The invocation context containing guild and message info
            prefix (str): The new prefix to set for the guild
        Returns:
            None
        Raises:
            Exception: If there is an error updating the database
        """
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
        """Shutdown the bot.

        This command allows authorized users to safely shut down the bot.
        It sends a confirmation message before closing the bot connection.

        Args:
            ctx (commands.Context): The command context containing information about the invocation.

        Returns:
            None: This function doesn't return anything.

        Example:
            !shut
        """
        await ctx.send("Đang tắt bot...")
        await ctx.bot.close()

async def setup(bot):
    await bot.add_cog(Sync(bot))
