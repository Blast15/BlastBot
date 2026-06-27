"""Canned responses / tags system cho tickets."""

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import success_embed, error_embed, create_embed
from utils.constants import COLORS
from cogs.moderation.base import require_guild_permissions
from .helpers import is_ticket_staff


class TicketTags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    managetags = app_commands.Group(
        name="managetags", description="Quản lý ticket tags",
        default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    @app_commands.command(name="tag", description="💬 Trả lời nhanh bằng tag mẫu")
    @app_commands.describe(tag_id="Mã tag cần gửi")
    @app_commands.guild_only()
    async def tag_cmd(self, interaction: discord.Interaction, tag_id: str):
        if interaction.guild is None or interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới dùng được tag.", ephemeral=True)

        content = await self.bot.db.get_tag(interaction.guild.id, tag_id)
        if not content:
            return await interaction.response.send_message(embed=error_embed("Lỗi", f"Không tìm thấy tag `{tag_id}`."), ephemeral=True)

        await interaction.response.send_message(content)

    @managetags.command(name="add", description="Thêm hoặc sửa tag mẫu")
    @require_guild_permissions(manage_guild=True)
    async def tag_add(self, interaction: discord.Interaction, tag_id: str, content: str):
        if interaction.guild is None:
            return
        clean_id = tag_id.lower().strip()
        await self.bot.db.add_tag(interaction.guild.id, clean_id, content)
        await interaction.response.send_message(embed=success_embed("Đã lưu tag", f"Tag `{clean_id}` đã sẵn sàng sử dụng."), ephemeral=True)

    @managetags.command(name="delete", description="Xóa tag mẫu")
    @require_guild_permissions(manage_guild=True)
    async def tag_delete(self, interaction: discord.Interaction, tag_id: str):
        if interaction.guild is None:
            return
        clean_id = tag_id.lower().strip()
        deleted = await self.bot.db.delete_tag(interaction.guild.id, clean_id)
        if deleted:
            await interaction.response.send_message(embed=success_embed("Đã xóa tag", f"Đã xóa tag `{clean_id}`."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed("Lỗi", f"Không tìm thấy tag `{clean_id}`."), ephemeral=True)

    @managetags.command(name="list", description="Xem danh sách tag mẫu")
    @require_guild_permissions(manage_guild=True)
    async def tag_list(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        tags = await self.bot.db.list_tags(interaction.guild.id)
        if not tags:
            return await interaction.response.send_message(
                embed=create_embed(title="Tags", description="Chưa có tag nào.", color=COLORS['info']), ephemeral=True)

        lines = [f"• `{t}`" for t in tags]
        await interaction.response.send_message(
            embed=create_embed(title="🏷️ Danh sách Tag", description="\n".join(lines), color=COLORS['info']), ephemeral=True)


async def setup(bot):
    await bot.add_cog(TicketTags(bot))
