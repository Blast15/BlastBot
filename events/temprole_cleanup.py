import discord
from discord.ext import tasks, commands
from discord.utils import utcnow

class TempRoleCleanup(commands.Cog):
    """A cog that handles automatic removal of temporary roles when they expire.
    This cog periodically checks for and removes temporary roles that have passed their
    expiration time. It queries a database table 'temprole' that stores temporary role
    assignments with their expiration timestamps.
    Attributes:
        bot: The Discord bot instance this cog is attached to.
        cleanup_temproles: A background task that runs every minute to check for expired roles.
    Methods:
        cleanup_temproles(): The main task that removes expired temporary roles.
        before_cleanup(): Ensures the bot is ready before starting the cleanup task.
    Database Schema:
        Table 'temprole' with columns:
            - guild_id: The Discord server ID
            - user_id: The member's Discord user ID 
            - role_id: The temporary role's ID
            - time: Unix timestamp for when the role should be removed
    Error Handling:
        - Logs errors during role removal operations
        - Safely handles missing members and roles
        - Continues operation even if individual role removals fail
    """

    def __init__(self, bot):
        self.bot = bot
        self.cleanup_temproles.start()

    @tasks.loop(minutes=1)
    async def cleanup_temproles(self):
        """
        Checks and removes expired temporary roles from guild members.
        This coroutine checks the database for any temporary roles that have expired and removes them 
        from the respective guild members. It also cleans up the database entries for expired roles.
        The function:
        1. Queries the database for expired temporary roles
        2. For each expired role:
            - Gets the guild and member objects
            - Removes the role from the member if still present
        3. Deletes the expired entries from the database
        Raises:
             Exception: Any error during role removal or database operations is logged but not raised
        Note:
             - Uses UTC timestamps for time comparison
             - Skips processing if guild/member/role is not found
             - Continues processing remaining roles if an error occurs with one role
        """
        try:
            current_time = utcnow().timestamp()
            
            # Lấy danh sách role hết hạn
            self.bot.db.cursor.execute(
                "SELECT guild_id, user_id, role_id FROM temprole WHERE time <= ?", 
                (current_time,)
            )
            expired_roles = self.bot.db.cursor.fetchall()
            
            if not expired_roles:
                return
                

            # Xử lý từng role
            for guild_id, user_id, role_id in expired_roles:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                # Lấy thông tin member                    
                try:
                    member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                except discord.NotFound:
                    continue
                
                # Lấy thông tin role
                role = guild.get_role(role_id)
                if not role:
                    continue

                # Gỡ role
                if role in member.roles:
                    try:
                        await member.remove_roles(role)
                    except Exception as e:
                        self.bot.logger.error(
                            f"Lỗi khi gỡ role {role.name}: {str(e)}"
                        )

            # Xóa dữ liệu cũ
            self.bot.db.cursor.execute("DELETE FROM temprole WHERE time <= ?", (current_time,))
            self.bot.db.conn.commit()

        except Exception as e:
            self.bot.logger.error(f"Lỗi trong cleanup_temproles: {str(e)}")

    @cleanup_temproles.before_loop
    async def before_cleanup(self):
        """
        An asynchronous method that ensures the bot is ready before any cleanup operations.

        This method is called before performing any role cleanup tasks and blocks until
        the bot's internal cache is ready to be used.

        Returns:
            None
        """
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TempRoleCleanup(bot))