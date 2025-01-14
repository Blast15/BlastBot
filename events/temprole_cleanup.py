import discord
from discord.ext import tasks, commands
from datetime import datetime

class TempRoleCleanup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cleanup_temproles.start()

    def cog_unload(self):
        self.cleanup_temproles.cancel()

    @tasks.loop(minutes=1)
    async def cleanup_temproles(self):
        current_time = datetime.utcnow().timestamp()
        self.bot.db.cursor.execute("SELECT guild_id, user_id, role_id FROM temprole WHERE time <= ?", (current_time,))
        expired_roles = self.bot.db.cursor.fetchall()

        for guild_id, user_id, role_id in expired_roles:
            guild = self.bot.get_guild(guild_id)
            if guild:
                member = guild.get_member(user_id)
                role = guild.get_role(role_id)
                if member and role:
                    try:
                        await member.remove_roles(role)
                    except discord.errors.Forbidden:
                        self.bot.logger.error(f"Không thể xóa role {role.name} từ {member.name} trong guild {guild.name}")

        # Xóa các role đã hết hạn khỏi cơ sở dữ liệu
        self.bot.db.cursor.execute("DELETE FROM temprole WHERE time <= ?", (current_time,))
        self.bot.db.conn.commit()

    @cleanup_temproles.before_loop
    async def before_cleanup_temproles(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(TempRoleCleanup(bot))