"""Clear/Purge command"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timedelta
from utils.embeds import success_embed, error_embed
from .base import BaseModerationCog, validate_amount


class ClearCommand(BaseModerationCog):
    """Clear messages command cog"""
    
    def __init__(self, bot):
        super().__init__(bot)
    
    @app_commands.command(
        name="clear",
        description="🧹 Xóa hàng loạt tin nhắn trong channel (1-100 messages)"
    )
    @app_commands.describe(amount="Số lượng tin nhắn cần xóa (1-100)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: int
    ):
        """Xóa tin nhắn"""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Validate permissions
            if not await self.validate_permissions(interaction, 'manage_messages'):
                return
            
            # Validate amount
            from utils.constants import CLEAR_CONFIG
            is_valid, error_msg = validate_amount(
                amount,
                CLEAR_CONFIG['min_messages'],
                CLEAR_CONFIG['max_messages']
            )
            if not is_valid:
                await self.send_error(interaction, error_msg or "Invalid amount", use_followup=True)
                return
            
            # Kiểm tra channel type
            if not isinstance(interaction.channel, discord.TextChannel):
                await self.send_error(interaction, "Lệnh này chỉ dùng trong text channel!", use_followup=True)
                return
            
            # Lấy tin nhắn để xóa
            messages = []
            async for message in interaction.channel.history(limit=amount):
                messages.append(message)
            
            if not messages:
                await self.send_error(interaction, "Không tìm thấy tin nhắn để xóa!", use_followup=True)
                return
            
            # Phân loại tin nhắn theo độ tuổi (Discord chỉ cho bulk delete tin nhắn < 14 ngày)
            from utils.constants import CLEAR_CONFIG
            two_weeks_ago = datetime.utcnow() - timedelta(days=CLEAR_CONFIG['message_age_limit_days'])
            bulk_delete_messages = [msg for msg in messages if msg.created_at.replace(tzinfo=None) > two_weeks_ago]
            old_messages = [msg for msg in messages if msg.created_at.replace(tzinfo=None) <= two_weeks_ago]
            
            deleted_count = 0
            
            # Xóa tin nhắn mới theo batch để tránh rate limit
            if bulk_delete_messages:
                from utils.constants import CLEAR_CONFIG
                # Xóa từng batch tin nhắn (giới hạn an toàn)
                batch_size = CLEAR_CONFIG['batch_size']
                for i in range(0, len(bulk_delete_messages), batch_size):
                    batch = bulk_delete_messages[i:i + batch_size]
                    try:
                        await interaction.channel.delete_messages(batch)
                        deleted_count += len(batch)
                        # Delay giữa các batch để tránh rate limit
                        if i + batch_size < len(bulk_delete_messages):
                            await asyncio.sleep(CLEAR_CONFIG['batch_delay_seconds'])
                    except discord.HTTPException as e:
                        self.logger.warning(f"Error deleting batch: {e}")
            
            # Xóa tin nhắn cũ từng cái một (chậm hơn)
            if old_messages:
                for message in old_messages:
                    try:
                        await message.delete()
                        deleted_count += 1
                        # Delay dài hơn cho tin nhắn cũ
                        await asyncio.sleep(CLEAR_CONFIG['old_message_delete_delay_seconds'])
                    except discord.HTTPException as e:
                        self.logger.warning(f"Error deleting old message: {e}")
            
            self.logger.info(f"{interaction.user} cleared {deleted_count} messages in {interaction.channel}")
            
            # Log moderation action
            if interaction.guild and isinstance(interaction.user, discord.Member):
                await self.log_moderation_action(
                    interaction.guild,
                    interaction.user,
                    "clear",
                    interaction.user,  # Clearer is both moderator and "target"
                    f"Cleared {deleted_count} messages",
                    f"Channel: {interaction.channel.mention if hasattr(interaction.channel, 'mention') else 'Unknown'}"
                )
            
            await interaction.followup.send(
                embed=success_embed(
                    "Đã xóa tin nhắn",
                    f"Đã xóa {deleted_count} tin nhắn."
                ),
                ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Error in clear command: {e}", exc_info=True)
            await self.send_error(interaction, f"Không thể xóa tin nhắn: {str(e)}", use_followup=True)


async def setup(bot):
    await bot.add_cog(ClearCommand(bot))
