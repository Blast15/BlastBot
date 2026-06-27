"""Tạo/gửi panel ticket."""

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import success_embed, error_embed, create_embed
from utils.constants import COLORS, TICKET_CONFIG
from cogs.moderation.base import require_guild_permissions
from .views import TicketPanelView


class TicketPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    panel = app_commands.Group(
        name="panel", description="Quản lý panel ticket",
        default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    @panel.command(name="create", description="Tạo panel ticket mới")
    @app_commands.describe(
        category="Category chứa ticket", title="Tiêu đề panel",
        content="Mô tả panel", button_label="Chữ trên nút",
        mention_role="Role được ping khi mở ticket")
    @require_guild_permissions(manage_guild=True)
    async def panel_create(self, interaction: discord.Interaction,
                           category: discord.CategoryChannel,
                           title: str = "Mở ticket!",
                           content: str = "Nhấn nút bên dưới để liên hệ đội ngũ hỗ trợ.",
                           button_label: str = "Tạo Ticket",
                           mention_role: discord.Role | None = None):
        if interaction.guild is None:
            return
        mentions = [mention_role.id] if mention_role else []
        pid = await self.bot.db.create_panel(
            interaction.guild.id, title=title, content=content,
            color=TICKET_CONFIG['default_color'], category_id=category.id,
            button_label=button_label, mention_on_open=mentions)
        await interaction.response.send_message(
            embed=success_embed("Đã tạo panel", f"**{title}** (ID `{pid}`)\n"
                                f"Dùng `/panel send panel_id:{pid} channel:#channel` để gửi panel."),
            ephemeral=True)

    @panel.command(name="send", description="Gửi panel vào channel chỉ định")
    @require_guild_permissions(manage_guild=True)
    async def panel_send(self, interaction: discord.Interaction, panel_id: int,
                         channel: discord.TextChannel):
        if interaction.guild is None:
            return
        panel = await self.bot.db.get_panel(panel_id)
        if not panel or panel['guild_id'] != interaction.guild.id:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Không tìm thấy panel."), ephemeral=True)

        embed = create_embed(
            title=panel['title'], description=panel['content'],
            color=panel['color'] or COLORS['primary'])

        view = TicketPanelView(self.bot)
        if panel.get('button_label'):
            view.create.label = panel['button_label']
        try:
            msg = await channel.send(embed=embed, view=view)
            await self.bot.db.set_panel_message(panel_id, channel.id, msg.id)
            await interaction.response.send_message(
                embed=success_embed("Đã gửi panel", f"Đã gửi panel vào {channel.mention}."), ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Lỗi", "Bot không có quyền gửi tin nhắn trong channel đó."), ephemeral=True)

    @panel.command(name="list", description="Liệt kê danh sách panel")
    @require_guild_permissions(manage_guild=True)
    async def panel_list(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        panels = await self.bot.db.list_panels(interaction.guild.id)
        if not panels:
            return await interaction.response.send_message(
                embed=create_embed(title="Panels", description="Chưa có panel nào.",
                                   color=COLORS['info']), ephemeral=True)
        lines = [f"`{p['panel_id']}` — **{p['title']}** (Category: <#{p['category_id']}>)" for p in panels]
        await interaction.response.send_message(
            embed=create_embed(title="📌 Ticket Panels", description="\n".join(lines),
                               color=COLORS['info']), ephemeral=True)


async def setup(bot):
    await bot.add_cog(TicketPanel(bot))
