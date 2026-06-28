"""Help command - Phân trang theo cog với nút điều hướng"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.constants import COLORS, EMOJIS
from utils.embeds import create_embed, info_embed

CATEGORY_META = {
    "Moderation": ("🛡️", "Quản lý server và thành viên"),
    "Tickets": ("🎫", "Hệ thống ticket hỗ trợ"),
    "Automation": ("🤖", "Lời chào, tạm biệt & auto-message"),
    "Utilities": ("🔧", "Công cụ tiện ích"),
    "Core": ("⚙️", "Lệnh cốt lõi của bot"),
    "Interactions": ("🖱️", "Context menu (chuột phải)"),
    "Other": ("📦", "Các lệnh khác"),
}


def categorize_commands(bot) -> dict[str, list[app_commands.Command]]:
    """Phân loại tất cả slash command theo module/cog."""
    categories: dict[str, list[app_commands.Command]] = {}
    for command in bot.tree.walk_commands():
        if not isinstance(command, app_commands.Command):
            continue
        binding = getattr(command, "binding", None)
        category = "Other"
        if binding and hasattr(binding, "__module__"):
            parts = binding.__module__.split(".")
            if len(parts) >= 2:
                category = parts[1].title()
        categories.setdefault(category, []).append(command)
    # sắp xếp lệnh trong mỗi category theo tên
    for cmds in categories.values():
        cmds.sort(key=lambda c: c.qualified_name)
    return categories


def build_overview_embed(bot, categories: dict) -> discord.Embed:
    total = sum(len(c) for c in categories.values())
    embed = create_embed(
        title=f"{EMOJIS.get('bot', '🤖')} Trung tâm trợ giúp",
        description=(
            f"Bot có **{total} lệnh** trong **{len(categories)} nhóm**.\n\n"
            "Dùng menu bên dưới để chọn nhóm lệnh, hoặc các nút để chuyển trang.\n"
            "Gõ `/help command:<tên>` để xem chi tiết một lệnh."
        ),
        color=COLORS["primary"],
    )
    for cat in sorted(categories):
        emoji, desc = CATEGORY_META.get(cat, ("📌", "Lệnh khác"))
        embed.add_field(
            name=f"{emoji} {cat} ({len(categories[cat])})",
            value=f"*{desc}*",
            inline=True,
        )
    embed.set_footer(text="Trang tổng quan")
    return embed


def build_category_embed(
    category: str, cmds: list, index: int, total_pages: int
) -> discord.Embed:
    emoji, desc = CATEGORY_META.get(category, ("📌", "Lệnh khác"))
    lines = []
    for cmd in cmds:
        cmd_desc = getattr(cmd, "description", None) or "Không có mô tả"
        lines.append(f"`/{cmd.qualified_name}`\n└ {cmd_desc}")
    embed = create_embed(
        title=f"{emoji} {category}",
        description=f"*{desc}*\n\n" + "\n\n".join(lines),
        color=COLORS["info"],
    )
    embed.set_footer(text=f"Nhóm {index + 1}/{total_pages} • {len(cmds)} lệnh")
    return embed


class HelpView(discord.ui.View):
    """Điều hướng help: dropdown chọn nhóm + nút Trước/Sau/Tổng quan."""

    def __init__(self, bot, author_id: int, categories: dict):
        super().__init__(timeout=180)
        self.bot = bot
        self.author_id = author_id
        self.categories = categories
        self.cat_names = sorted(categories)
        self.current = -1  # -1 = trang tổng quan

        # Dropdown chọn category
        options = [
            discord.SelectOption(
                label=cat,
                description=CATEGORY_META.get(cat, ("", "Lệnh khác"))[1][:90],
                emoji=CATEGORY_META.get(cat, ("📌", ""))[0],
                value=str(i),
            )
            for i, cat in enumerate(self.cat_names)
        ]
        self.select = discord.ui.Select(
            placeholder="📂 Chọn nhóm lệnh...", options=options
        )
        self.select.callback = self._on_select
        self.add_item(self.select)
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Đây không phải bảng trợ giúp của bạn, hãy gõ `/help` để mở của riêng bạn.",
                ephemeral=True,
            )
            return False
        return True

    def _update_buttons(self):
        self.prev_btn.disabled = self.current <= -1
        self.next_btn.disabled = self.current >= len(self.cat_names) - 1
        self.home_btn.disabled = self.current == -1

    def _current_embed(self) -> discord.Embed:
        if self.current == -1:
            return build_overview_embed(self.bot, self.categories)
        cat = self.cat_names[self.current]
        return build_category_embed(
            cat, self.categories[cat], self.current, len(self.cat_names)
        )

    async def _refresh(self, interaction: discord.Interaction):
        self._update_buttons()
        await interaction.response.edit_message(embed=self._current_embed(), view=self)

    async def _on_select(self, interaction: discord.Interaction):
        self.current = int(self.select.values[0])
        await self._refresh(interaction)

    @discord.ui.button(
        label="Tổng quan", emoji="🏠", style=discord.ButtonStyle.secondary
    )
    async def home_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current = -1
        await self._refresh(interaction)

    @discord.ui.button(label="Trước", emoji="◀️", style=discord.ButtonStyle.primary)
    async def prev_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current = max(-1, self.current - 1)
        await self._refresh(interaction)

    @discord.ui.button(label="Sau", emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.current = min(len(self.cat_names) - 1, self.current + 1)
        await self._refresh(interaction)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("BlastBot.Core.Help")

    @app_commands.command(name="help", description="Hiển thị danh sách lệnh của bot")
    @app_commands.describe(command="Tên lệnh cần xem chi tiết (tùy chọn)")
    async def help(self, interaction: discord.Interaction, command: str | None = None):
        try:
            if command:
                await self._show_command_help(interaction, command)
                return

            categories = categorize_commands(self.bot)
            if not categories:
                await interaction.response.send_message(
                    embed=info_embed("Không tìm thấy lệnh nào!"), ephemeral=True
                )
                return

            view = HelpView(self.bot, interaction.user.id, categories)
            await interaction.response.send_message(
                embed=build_overview_embed(self.bot, categories),
                view=view,
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error in help command: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    embed=info_embed(f"Lỗi: {e}"), ephemeral=True
                )

    async def _show_command_help(
        self, interaction: discord.Interaction, command_name: str
    ):
        cmd = None
        for c in self.bot.tree.walk_commands():
            if isinstance(
                c, app_commands.Command
            ) and c.qualified_name == command_name.lstrip("/"):
                cmd = c
                break
        if not cmd:
            await interaction.response.send_message(
                embed=info_embed(
                    f"Lệnh `{command_name}` không tồn tại!",
                    "Gõ `/help` để xem danh sách lệnh.",
                ),
                ephemeral=True,
            )
            return

        embed = create_embed(
            title=f"📖 /{cmd.qualified_name}",
            description=getattr(cmd, "description", None) or "Không có mô tả",
            color=COLORS["info"],
        )

        params = getattr(cmd, "parameters", [])
        if params:
            lines = []
            for p in params:
                req = "**Bắt buộc**" if getattr(p, "required", False) else "*Tùy chọn*"
                pdesc = getattr(p, "description", None) or "Không có mô tả"
                lines.append(f"• `{getattr(p, 'name', 'param')}` ({req}): {pdesc}")
            embed.add_field(name="⚙️ Tham số", value="\n".join(lines), inline=False)

        usage_parts = [
            f"<{getattr(p, 'name', 'p')}>"
            if getattr(p, "required", False)
            else f"[{getattr(p, 'name', 'p')}]"
            for p in params
        ]
        usage = f"`/{cmd.qualified_name} {' '.join(usage_parts)}`".strip()
        embed.add_field(name="💡 Cách dùng", value=usage, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
