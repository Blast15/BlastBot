"""Temprole command - gán role tạm thời, tự gỡ sau thời gian định trước"""

import discord
from discord import app_commands
from discord.ext import tasks
from datetime import datetime, timedelta, timezone

from utils.embeds import success_embed
from utils.constants import COMMAND_COOLDOWNS
from .base import BaseModerationCog, validate_duration


class TempRoleCommand(BaseModerationCog):
    """Temprole command cog"""

    def __init__(self, bot):
        super().__init__(bot)
        self.check_expired_roles.start()

    async def cog_unload(self):
        self.check_expired_roles.cancel()

    @app_commands.command(
        name="temprole",
        description="⏳ Gán role tạm thời cho member (tự gỡ sau thời gian định trước)"
    )
    @app_commands.describe(
        member="Member cần gán role",
        role="Role cần gán",
        duration="Thời gian giữ role (phút)",
        reason="Lý do"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.cooldown(1, COMMAND_COOLDOWNS['timeout'], key=lambda i: i.user.id)
    async def temprole(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        duration: int,
        reason: str = "Không có lý do"
    ):
        """Gán role tạm thời"""
        try:
            if not await self.validate_permissions(interaction, 'manage_roles'):
                return

            guild = interaction.guild
            if guild is None or not isinstance(interaction.user, discord.Member):
                await self.send_error(interaction, "Không xác định được guild/member!")
                return

            # Validate duration: 1 phút - 28 ngày
            is_valid, _ = validate_duration(duration, 1, 40320)
            if not is_valid:
                await self.send_error(interaction, "Thời gian phải từ 1 phút đến 28 ngày (40320 phút)!")
                return

            # Kiểm tra hierarchy của role với người dùng
            if role >= interaction.user.top_role and interaction.user.id != guild.owner_id:
                await self.send_error(interaction, "Role này cao hơn hoặc bằng role cao nhất của bạn!")
                return

            # Kiểm tra hierarchy của bot
            bot_member = guild.get_member(self.bot.user.id) if self.bot.user else None
            if bot_member and role >= bot_member.top_role:
                await self.send_error(interaction, "Role này cao hơn hoặc bằng role cao nhất của bot!")
                return

            if role.managed:
                await self.send_error(interaction, "Không thể gán role được quản lý bởi tích hợp (bot/booster)!")
                return

            await interaction.response.defer(ephemeral=True)

            await member.add_roles(role, reason=f"Temprole bởi {interaction.user}: {reason}")

            expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration)
            await self.bot.db.add_temp_role(guild.id, member.id, role.id, expires_at)

            self.logger.info(
                f"{interaction.user} gave temp role {role} to {member} for {duration}m"
            )

            await self.log_moderation_action(
                guild,
                interaction.user,
                "temprole",
                member,
                reason,
                f"Role: {role.name} | Duration: {duration} minutes"
            )

            await interaction.followup.send(
                embed=success_embed(
                    "Đã gán temprole",
                    f"Đã gán {role.mention} cho {member.mention} trong **{duration} phút**.\n"
                    f"Hết hạn: <t:{int(expires_at.timestamp())}:R>\n"
                    f"**Lý do:** {reason}"
                ),
                ephemeral=True
            )
        except discord.Forbidden:
            await self.safe_error_response(interaction, "Lỗi", "Bot không có quyền quản lý role này!")
        except Exception as e:
            self.logger.error(f"Error in temprole command: {e}", exc_info=True)
            await self.safe_error_response(interaction, "Lỗi", f"Không thể gán temprole: {str(e)}")

    @tasks.loop(minutes=1)
    async def check_expired_roles(self):
        """Quét và gỡ các temp role đã hết hạn."""
        db = getattr(self.bot, 'db', None)
        if db is None:
            return

        try:
            expired = await db.get_expired_temp_roles()
            for entry in expired:
                guild = self.bot.get_guild(entry['guild_id'])
                if not guild:
                    await db.remove_temp_role(entry['guild_id'], entry['user_id'], entry['role_id'])
                    continue

                member = guild.get_member(entry['user_id'])
                role = guild.get_role(entry['role_id'])

                if member and role and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="Temprole hết hạn")
                        self.logger.info(f"Đã gỡ temp role {role} khỏi {member}")
                    except discord.HTTPException as e:
                        self.logger.warning(f"Không thể gỡ temp role: {e}")

                await db.remove_temp_role(entry['guild_id'], entry['user_id'], entry['role_id'])
        except Exception as e:
            self.logger.error(f"Lỗi khi quét temp roles: {e}", exc_info=True)

    @check_expired_roles.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TempRoleCommand(bot))
