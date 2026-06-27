"""Clear/Purge command"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from utils.embeds import success_embed, error_embed
from utils.constants import CLEAR_CONFIG, COMMAND_COOLDOWNS
from utils.error_handler import validate_number_range, ValidationError
from .base import BaseModerationCog, require_guild_permissions


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
    @require_guild_permissions(manage_messages=True)
    @app_commands.checks.cooldown(1, COMMAND_COOLDOWNS['clear'], key=lambda i: i.user.id)
    async def clear(
        self,
        interaction: discord.Interaction,
        amount: int
    ):
        """Xóa tin nhắn"""
        try:
            # Validate amount
            validate_number_range(
                amount,
                CLEAR_CONFIG['min_messages'],
                CLEAR_CONFIG['max_messages'],
                "Số lượng tin nhắn"
            )
            
            # Kiểm tra channel type
            if not isinstance(interaction.channel, discord.TextChannel):
                await self.send_error(interaction, "Lệnh này chỉ dùng trong text channel!")
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Lấy tin nhắn để xóa, bỏ qua pinned messages
            messages = []
            async for message in interaction.channel.history(limit=amount):
                if message.pinned:
                    continue
                messages.append(message)
            
            if not messages:
                await self.send_error(interaction, "Không tìm thấy tin nhắn để xóa!", use_followup=True)
                return
            
            # Phân loại tin nhắn theo độ tuổi
            two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=CLEAR_CONFIG['message_age_limit_days'])
            bulk_delete_messages = [msg for msg in messages if msg.created_at > two_weeks_ago]
            old_messages = [msg for msg in messages if msg.created_at <= two_weeks_ago]
            
            deleted_count = 0
            
            # Xóa tin nhắn mới theo batch để tránh rate limit
            if bulk_delete_messages:
                batch_size = CLEAR_CONFIG['batch_size']
                for i in range(0, len(bulk_delete_messages), batch_size):
                    batch = bulk_delete_messages[i:i + batch_size]
                    try:
                        if len(batch) == 1:
                            await batch[0].delete()
                        else:
                            await interaction.channel.delete_messages(batch)
                        deleted_count += len(batch)
                        if i + batch_size < len(bulk_delete_messages):
                            await asyncio.sleep(CLEAR_CONFIG['batch_delay_seconds'])
                    except discord.HTTPException as e:
                        self.logger.warning(f"Error deleting batch: {e}")
            
            # Xóa tin nhắn cũ từng cái một
            if old_messages:
                for message in old_messages:
                    try:
                        await message.delete()
                        deleted_count += 1
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
                    target=None,
                    reason=f"Đã xóa {deleted_count} tin nhắn trong #{interaction.channel.name}",
                )
            
            await interaction.followup.send(
                embed=success_embed(
                    "Đã xóa tin nhắn",
                    f"Đã xóa {deleted_count} tin nhắn."
                ),
                ephemeral=True
            )
        except ValidationError as e:
            await self.send_error(interaction, e.user_message)
        except Exception as e:
            self.logger.error(f"Error in clear command: {e}", exc_info=True)
            await self.safe_error_response(interaction, "Lỗi", f"Không thể xóa tin nhắn: {str(e)}")


async def setup(bot):
    await bot.add_cog(ClearCommand(bot))
