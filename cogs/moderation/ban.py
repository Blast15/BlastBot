"""Ban command"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.embeds import success_embed, error_embed, warning_embed
from utils.views import ConfirmView
from .base import BaseModerationCog, validate_amount


BAN_REASONS = [
    "Vi phạm nghiêm trọng",
    "Spam liên tục",
    "Raid/Nuke server",
    "Alt account",
    "Scam/Phishing",
    "Hate speech",
]


async def ban_reason_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete cho ban reason"""
    filtered = [r for r in BAN_REASONS if current.lower() in r.lower()]
    return [
        app_commands.Choice(name=reason, value=reason)
        for reason in filtered[:25]
    ]


class BanCommand(BaseModerationCog):
    """Ban command cog"""
    
    def __init__(self, bot):
        super().__init__(bot)
    
    @app_commands.command(
        name="ban",
        description="🔨 Ban member khỏi server vĩnh viễn (không thể join lại)"
    )
    @app_commands.describe(
        member="Member cần ban",
        reason="Lý do ban",
        delete_messages="Xóa tin nhắn trong bao nhiêu ngày (0-7)"
    )
    @app_commands.autocomplete(reason=ban_reason_autocomplete)
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "Không có lý do",
        delete_messages: int = 0
    ):
        """Ban member khỏi server"""
        try:
            # Validate permissions
            if not await self.validate_permissions(interaction, 'ban_members'):
                return
            
            # Validate target
            is_valid, error_msg = await self.validate_target(interaction, member)
            if not is_valid:
                await self.send_error(interaction, error_msg or "Invalid target")
                return
            
            # Validate hierarchy
            is_valid, error_msg = await self.validate_hierarchy(interaction, member, "ban member này")
            if not is_valid:
                await self.send_error(interaction, error_msg or "Hierarchy check failed")
                return
            
            # Validate delete_messages
            is_valid, error_msg = validate_amount(delete_messages, 0, 7)
            if not is_valid:
                await self.send_error(interaction, error_msg or "Invalid amount")
                return
            delete_messages = max(0, min(7, delete_messages))
            
            # Xác nhận
            view = ConfirmView(interaction.user)
            await interaction.response.send_message(
                embed=warning_embed(
                    "Xác nhận ban",
                    f"Bạn có chắc muốn ban {member.mention}?\n"
                    f"**Lý do:** {reason}\n"
                    f"**Xóa tin nhắn:** {delete_messages} ngày"
                ),
                view=view,
                ephemeral=True
            )
            
            await view.wait()
            
            if not view.value:
                await interaction.edit_original_response(
                    embed=error_embed("Đã hủy", "Đã hủy thao tác ban."),
                    view=None
                )
                return
            
            # Thực hiện ban
            await member.ban(
                reason=f"{interaction.user}: {reason}",
                delete_message_days=delete_messages
            )
            
            self.logger.info(f"{interaction.user} banned {member} - Reason: {reason}")
            
            # Log moderation action
            if interaction.guild and isinstance(interaction.user, discord.Member):
                await self.log_moderation_action(
                    interaction.guild,
                    interaction.user,
                    "ban",
                    member,
                    reason,
                    f"Delete messages: {delete_messages} days"
                )
            
            await interaction.edit_original_response(
                embed=success_embed(
                    "Đã ban",
                    f"{member.mention} đã được ban khỏi server.\n**Lý do:** {reason}"
                ),
                view=None
            )
        except Exception as e:
            self.logger.error(f"Error in ban command: {e}", exc_info=True)
            await interaction.edit_original_response(
                embed=error_embed("Lỗi", f"Không thể ban: {str(e)}"),
                view=None
            )


async def setup(bot):
    await bot.add_cog(BanCommand(bot))
