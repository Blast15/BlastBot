"""Tạo/gửi panel và quản lý form."""

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
    form = app_commands.Group(
        name="form", description="Quản lý form ticket",
        default_permissions=discord.Permissions(manage_guild=True), guild_only=True)

    # ---- forms ----
    @form.command(name="create", description="Tạo form mới (rồi thêm field)")
    @require_guild_permissions(manage_guild=True)
    async def form_create(self, interaction: discord.Interaction, title: str):
        if interaction.guild is None:
            return
        fid = await self.bot.db.create_form(interaction.guild.id, title)
        await interaction.response.send_message(
            embed=success_embed("Đã tạo form", f"**{title}** (ID `{fid}`)\n"
                                f"Dùng `/form addfield form_id:{fid}` để thêm câu hỏi."),
            ephemeral=True)

    @form.command(name="addfield", description="Thêm câu hỏi vào form (tối đa 5)")
    @app_commands.choices(style=[
        app_commands.Choice(name="Ngắn", value="short"),
        app_commands.Choice(name="Dài", value="paragraph")])
    @require_guild_permissions(manage_guild=True)
    async def form_addfield(self, interaction: discord.Interaction, form_id: int,
                            label: str, style: app_commands.Choice[str],
                            placeholder: str = "", required: bool = True):
        if interaction.guild is None:
            return
        fields = await self.bot.db.get_form_fields(form_id)
        if len(fields) >= 5:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Form đã đủ 5 câu hỏi (giới hạn Discord)."), ephemeral=True)
        await self.bot.db.add_form_field(form_id, label, placeholder, style.value,
                                         required, len(fields))
        await interaction.response.send_message(
            embed=success_embed("Đã thêm câu hỏi", f"`{label}` ({style.name})"), ephemeral=True)

    @form.command(name="list", description="Liệt kê form")
    @require_guild_permissions(manage_guild=True)
    async def form_list(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        forms = await self.bot.db.list_forms(interaction.guild.id)
        if not forms:
            return await interaction.response.send_message(
                embed=create_embed(title="Forms", description="Chưa có form nào.",
                                   color=COLORS['info']), ephemeral=True)
        lines = [f"`{f['form_id']}` — {f['title']}" for f in forms]
        await interaction.response.send_message(
            embed=create_embed(title="📋 Forms", description="\n".join(lines),
                               color=COLORS['info']), ephemeral=True)

    # ---- panels ----
    @panel.command(name="create", description="Tạo panel ticket mới")
    @app_commands.describe(
        category="Category chứa ticket", title="Tiêu đề panel",
        content="Mô tả panel", button_label="Chữ trên nút",
        form_id="ID form (tùy chọn)", mention_role="Role được ping khi mở ticket")
    @require_guild_permissions(manage_guild=True)
    async def panel_create(self, interaction: discord.Interaction,
                           category: discord.CategoryChannel,
                           title: str = "Mở ticket!",
                           content: str = "Nhấn nút bên dưới để liên hệ đội ngũ hỗ trợ.",
                           button_label: str = "Tạo Ticket",
                           form_id: int | None = None,
                           mention_role: discord.Role | None = None):
        if interaction.guild is None:
            return
        mentions = [mention_role.id] if mention_role else []
        pid = await self.bot.db.create_panel(
            interaction.guild.id, title=title, content=content,
            color=TICKET_CONFIG['default_color'], category_id=category.id,
            button_label=button_label, form_id=form_id,
            mention_on_open=mentions)
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
            title=panel['title'],
            description=panel['content'],
            color=panel['color'] or COLORS['primary']
        )
        
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
