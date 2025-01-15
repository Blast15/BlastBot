import discord
from discord.ext import commands
import asyncio
from discord.utils import utcnow

class TempRoleCleanup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduled_tasks = {}  # Chứa các task được lên lịch
        self.bot.loop.create_task(self.initialize_tasks())

    async def initialize_tasks(self):
        """
        Initializes and schedules temporary role removal tasks from the database.
        This coroutine is called when the bot starts up to restore any temporary role removal
        tasks that were saved in the database from a previous session. It:
        1. Waits for the bot to be ready
        2. Retrieves all temporary role entries from database
        3. Schedules removal tasks for each entry based on remaining time
        Parameters
        ----------
        self : TempRole
            The TempRole cog instance
        Returns
        -------
        None
        Note
        ----
        The method uses the bot's database to fetch existing temporary roles and
        schedules their removal using schedule_role_removal()
        """
        await self.bot.wait_until_ready()
        current_time = utcnow().timestamp()
        
        self.bot.db.cursor.execute("SELECT guild_id, user_id, role_id, time FROM temprole")
        existing_roles = self.bot.db.cursor.fetchall()
        
        for guild_id, user_id, role_id, removal_time in existing_roles:
            delay = max(0, removal_time - current_time)
            self.schedule_role_removal(guild_id, user_id, role_id, delay)

    def schedule_role_removal(self, guild_id, user_id, role_id, delay):
        """
        Schedule the removal of a temporary role from a user after a specified delay.
        Args:
            guild_id (int): The ID of the Discord guild (server)
            user_id (int): The ID of the user to remove the role from
            role_id (int): The ID of the role to remove
            delay (float): The delay in seconds before removing the role
        Notes:
            - If there's an existing scheduled task for the same (guild, user, role) combination,
              it will be cancelled before creating a new one
            - The task is stored in self.scheduled_tasks with (guild_id, user_id, role_id) as the key
        """
        task_key = (guild_id, user_id, role_id)
        
        if task_key in self.scheduled_tasks:
            self.scheduled_tasks[task_key].cancel()
        
        task = self.bot.loop.create_task(
            self._remove_role_later(guild_id, user_id, role_id, delay)
        )
        self.scheduled_tasks[task_key] = task

    async def _remove_role_later(self, guild_id, user_id, role_id, delay):
        """
        Asynchronously removes a role from a user after a specified delay.
        This method handles the delayed removal of a role from a user, including database cleanup
        and task management. It will attempt to find the guild, member, and role, and if all
        exist, remove the role after the specified delay.
        Parameters:
            guild_id (int): The ID of the guild (server) where the role removal will occur
            user_id (int): The ID of the user to remove the role from
            role_id (int): The ID of the role to be removed
            delay (float): The time in seconds to wait before removing the role
        Returns:
            None
        Raises:
            No explicit raises, all exceptions are caught and logged internally
        Note:
            - If the guild, member, or role cannot be found, the function will exit silently
            - The function will also clean up the associated database entry and scheduled task
            - Any exceptions during execution are logged but not propagated
        """
        try:
            await asyncio.sleep(delay)
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            try:
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            except discord.NotFound:
                return

            role = guild.get_role(role_id)
            if not role:
                return

            if role in member.roles:
                await member.remove_roles(role)
                
            self.bot.db.cursor.execute(
                "DELETE FROM temprole WHERE guild_id=? AND user_id=? AND role_id=?",
                (guild_id, user_id, role_id)
            )
            self.bot.db.conn.commit()
            
            task_key = (guild_id, user_id, role_id)
            self.scheduled_tasks.pop(task_key, None)

        except Exception as e:
            self.bot.logger.error(f"Error in _remove_role_later: {str(e)}")

    async def add_temp_role(self, guild_id, user_id, role_id, duration):
        """
        Adds a temporary role to a user in a guild with a specified duration.
        This method both stores the temporary role information in the database and schedules its removal.
        Parameters
        ----------
        guild_id : int
            The ID of the guild where the role will be added
        user_id : int
            The ID of the user who will receive the temporary role
        role_id : int
            The ID of the role to be temporarily assigned
        duration : float
            The duration in seconds for how long the role should remain
        Returns
        -------
        None
        Notes
        -----
        The role removal time is stored in UTC timestamp format.
        The role removal is scheduled using schedule_role_removal method.
        """
        removal_time = utcnow().timestamp() + duration
        
        self.bot.db.cursor.execute(
            "INSERT INTO temprole (guild_id, user_id, role_id, time) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, role_id, removal_time)
        )
        self.bot.db.conn.commit()
        
        self.schedule_role_removal(guild_id, user_id, role_id, duration)

async def setup(bot):
    await bot.add_cog(TempRoleCleanup(bot))