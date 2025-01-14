import discord
from discord.ext import tasks, commands
from discord.utils import utcnow

class TempRoleCleanup(commands.Cog):
    """Xử lý tự động gỡ role tạm thời khi hết hạn"""

    def __init__(self, bot):
        self.bot = bot
        self.cleanup_temproles.start()
        self.bot.logger.info("Đã khởi tạo TempRoleCleanup")

    @tasks.loop(minutes=1)
    async def cleanup_temproles(self):
        """Kiểm tra và gỡ các role tạm thời đã hết hạn"""
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
                
            self.bot.logger.info(f"Tìm thấy {len(expired_roles)} role cần gỡ")

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
                        self.bot.logger.info(
                            f"Đã gỡ role {role.name} của {member.name} trong {guild.name}"
                        )
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
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.cleanup_temproles.cancel()

async def setup(bot):
    await bot.add_cog(TempRoleCleanup(bot))