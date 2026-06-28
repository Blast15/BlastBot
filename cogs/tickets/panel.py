"""Tạo/gửi panel ticket."""

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.base import require_guild_permissions
from utils.constants import COLORS, TICKET_CONFIG
from utils.embeds import create_embed, error_embed, success_embed

from .views import TicketPanelView


class TicketPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    panel = app_commands.Group(
        name="panel",
        description="Quản lý panel ticket",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    @panel.command(name="create", description="Tạo panel ticket mới")
    @app_commands.describe(
        category="Category chứa ticket",
        title="Tiêu đề panel",
        content="Mô tả panel",
        button_label="Chữ trên nút",
        mention_role="Role được ping khi mở ticket",
    )
    @require_guild_permissions(manage_guild=True)
    async def panel_create(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        title: str = "Mở ticket!",
        content: str = "Nhấn nút bên dưới để liên hệ đội ngũ hỗ trợ.",
        button_label: str = "Tạo Ticket",
        mention_role: discord.Role | None = None,
    ):
        if interaction.guild is None:
            return
        mentions = [mention_role.id] if mention_role else []
        pid = await self.bot.db.create_panel(
            interaction.guild.id,
            title=title,
            content=content,
            color=TICKET_CONFIG["default_color"],
            category_id=category.id,
            button_label=button_label,
            mention_on_open=mentions,
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Đã tạo panel",
                f"**{title}** (ID `{pid}`)\n"
                f"Dùng `/panel send panel_id:{pid} channel:#channel` để gửi panel.",
            ),
            ephemeral=True,
        )

    @panel.command(name="send", description="Gửi panel vào channel chỉ định")
    @require_guild_permissions(manage_guild=True)
    async def panel_send(
        self,
        interaction: discord.Interaction,
        panel_id: int,
        channel: discord.TextChannel,
    ):
        if interaction.guild is None:
            return
        panel = await self.bot.db.get_panel(panel_id)
        if not panel or panel["guild_id"] != interaction.guild.id:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Không tìm thấy panel."), ephemeral=True
            )

        embed = create_embed(
            title=panel["title"],
            description=panel["content"],
            color=panel["color"] or COLORS["primary"],
        )

        view = TicketPanelView(
            self.bot,
            button_label=panel.get("button_label"),
            button_emoji=panel.get("button_emoji"),
        )
        try:
            msg = await channel.send(embed=embed, view=view)
            await self.bot.db.set_panel_message(panel_id, channel.id, msg.id)
            await interaction.response.send_message(
                embed=success_embed(
                    "Đã gửi panel", f"Đã gửi panel vào {channel.mention}."
                ),
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed(
                    "Lỗi", "Bot không có quyền gửi tin nhắn trong channel đó."
                ),
                ephemeral=True,
            )

    @panel.command(name="list", description="Liệt kê danh sách panel")
    @require_guild_permissions(manage_guild=True)
    async def panel_list(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        panels = await self.bot.db.list_panels(interaction.guild.id)
        if not panels:
            return await interaction.response.send_message(
                embed=create_embed(
                    title="Panels",
                    description="Chưa có panel nào.",
                    color=COLORS["info"],
                ),
                ephemeral=True,
            )
        lines = [
            f"`{p['panel_id']}` — **{p['title']}** (Category: <#{p['category_id']}>)"
            for p in panels
        ]
        await interaction.response.send_message(
            embed=create_embed(
                title="📌 Ticket Panels",
                description="\n".join(lines),
                color=COLORS["info"],
            ),
            ephemeral=True,
        )

    @panel.command(name="edit", description="Sửa nội dung panel (tiêu đề, mô tả, nút)")
    @app_commands.describe(
        panel_id="ID panel cần sửa",
        title="Tiêu đề mới",
        content="Mô tả mới",
        button_label="Chữ nút mới",
    )
    @require_guild_permissions(manage_guild=True)
    async def panel_edit(
        self,
        interaction: discord.Interaction,
        panel_id: int,
        title: str | None = None,
        content: str | None = None,
        button_label: str | None = None,
    ):
        if interaction.guild is None:
            return
        panel = await self.bot.db.get_panel(panel_id)
        if not panel or panel["guild_id"] != interaction.guild.id:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Không tìm thấy panel."), ephemeral=True
            )

        updated = await self.bot.db.update_panel(
            panel_id, title=title, content=content, button_label=button_label
        )
        if not updated:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Bạn chưa nhập trường nào để sửa."),
                ephemeral=True,
            )

        # Cập nhật message panel đang hiển thị (nếu còn)
        await self._refresh_panel_message(interaction.guild, panel_id)
        await interaction.response.send_message(
            embed=success_embed(
                "Đã sửa panel", f"Panel `{panel_id}` đã được cập nhật."
            ),
            ephemeral=True,
        )

    @panel.command(name="delete", description="Xóa panel (kèm message nếu còn)")
    @app_commands.describe(panel_id="ID panel cần xóa")
    @require_guild_permissions(manage_guild=True)
    async def panel_delete(self, interaction: discord.Interaction, panel_id: int):
        if interaction.guild is None:
            return
        panel = await self.bot.db.get_panel(panel_id)
        if not panel or panel["guild_id"] != interaction.guild.id:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Không tìm thấy panel."), ephemeral=True
            )

        # Cố xóa message panel nếu còn tồn tại
        if panel.get("channel_id") and panel.get("message_id"):
            channel = interaction.guild.get_channel(panel["channel_id"])
            if isinstance(channel, discord.TextChannel):
                try:
                    msg = await channel.fetch_message(panel["message_id"])
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass  # admin đã xóa tay rồi, bỏ qua

        await self.bot.db.delete_panel(panel_id)
        await interaction.response.send_message(
            embed=success_embed("Đã xóa panel", f"Panel `{panel_id}` đã được xóa."),
            ephemeral=True,
        )

    async def _refresh_panel_message(self, guild: discord.Guild, panel_id: int):
        """Cập nhật lại embed của message panel đang hiển thị (nếu còn)."""
        panel = await self.bot.db.get_panel(panel_id)
        if not panel or not panel.get("channel_id") or not panel.get("message_id"):
            return
        channel = guild.get_channel(panel["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            msg = await channel.fetch_message(panel["message_id"])
            embed = create_embed(
                title=panel["title"],
                description=panel["content"],
                color=panel["color"] or COLORS["primary"],
            )
            view = TicketPanelView(
                self.bot,
                button_label=panel.get("button_label"),
                button_emoji=panel.get("button_emoji"),
            )
            await msg.edit(embed=embed, view=view)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot):
    await bot.add_cog(TicketPanel(bot))
