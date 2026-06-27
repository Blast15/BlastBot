"""Softban command - ban rồi unban ngay để xóa tin nhắn gần đây"""

import discord
from discord import app_commands

from utils.embeds import success_embed, error_embed, warning_embed
from utils.views import ConfirmView
from utils.constants import COMMAND_COOLDOWNS
from .base import BaseModerationCog, validate_amount


class SoftbanCommand(BaseModerationCog):
    """Softban command cog"""

    def __init__(self, bot):
        super().__init__(bot)

    @app_commands.command(
        name="softban",
        description="🧹 Softban: ban rồi unban ngay để xóa tin nhắn gần đây (member có thể join lại)"
    )
    @app_commands.describe(
        member="Member cần softban",
        reason="Lý do softban",
        delete_messages="Xóa tin nhắn trong bao nhiêu ngày (1-7)"
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, COMMAND_COOLDOWNS['ban'], key=lambda i: i.user.id)
    async def softban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Không có lý do",
        delete_messages: int = 1
    ):
        """Softban member"""
        try:
            if not await self.validate_permissions(interaction, 'ban_members'):
                return

            is_valid, error_msg = await self.validate_target(interaction, member)
            if not is_valid:
                await self.send_error(interaction, error_msg or "Invalid target")
                return

            is_valid, error_msg = await self.validate_hierarchy(interaction, member, "softban member này")
            if not is_valid:
                await self.send_error(interaction, error_msg or "Hierarchy check failed")
                return

            is_valid, error_msg = validate_amount(delete_messages, 1, 7)
            if not is_valid:
                await self.send_error(interaction, error_msg or "Invalid amount")
                return
            delete_messages = max(1, min(7, delete_messages))

            view = ConfirmView(interaction.user)
            await interaction.response.send_message(
                embed=warning_embed(
                    "Xác nhận softban",
                    f"Bạn có chắc muốn softban {member.mention}?\n"
                    f"**Lý do:** {reason}\n"
                    f"**Xóa tin nhắn:** {delete_messages} ngày\n"
                    f"*(Member sẽ bị ban rồi unban ngay, có thể join lại)*"
                ),
                view=view,
                ephemeral=True
            )

            await view.wait()

            if not view.value:
                await interaction.edit_original_response(
                    embed=error_embed("Đã hủy", "Đã hủy thao tác softban."),
                    view=None
                )
                return

            guild = interaction.guild
            if guild is None:
                await self.safe_error_response(interaction, "Lỗi", "Không xác định được guild!")
                return

            # Ban để xóa tin nhắn, rồi unban ngay
            await guild.ban(
                member,
                reason=f"Softban bởi {interaction.user}: {reason}",
                delete_message_seconds=delete_messages * 86400
            )
            await guild.unban(
                discord.Object(id=member.id),
                reason=f"Softban (unban tự động) bởi {interaction.user}"
            )

            self.logger.info(f"{interaction.user} softbanned {member} - Reason: {reason}")

            if isinstance(interaction.user, discord.Member):
                await self.log_moderation_action(
                    guild,
                    interaction.user,
                    "softban",
                    member,
                    reason,
                    f"Delete messages: {delete_messages} days"
                )

            await interaction.edit_original_response(
                embed=success_embed(
                    "Đã softban",
                    f"{member.mention} đã bị softban (tin nhắn {delete_messages} ngày đã xóa).\n"
                    f"**Lý do:** {reason}"
                ),
                view=None
            )
        except Exception as e:
            self.logger.error(f"Error in softban command: {e}", exc_info=True)
            await self.safe_error_response(interaction, "Lỗi", f"Không thể softban: {str(e)}")
