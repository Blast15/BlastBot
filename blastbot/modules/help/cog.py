from __future__ import annotations

from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from blastbot import __version__
from blastbot.core.bot import BlastBot
from blastbot.shared.embeds import PRIMARY, error, info
from blastbot.shared.ui import SafeView

CATEGORY_NAMES = {
    "Automation": "⚡ Tự động hóa",
    "Configuration": "⚙️ Cấu hình",
    "Help": "📚 Trợ giúp",
    "Moderation": "🛡️ Kiểm duyệt",
    "Reddit": "📰 Reddit",
    "Roles": "🎭 Role",
}


def _category(command: app_commands.Command[object, ..., object]) -> str:
    binding = command.binding
    return binding.__class__.__name__.removesuffix("Cog") if binding is not None else "Khác"


def _footer(card: discord.Embed) -> discord.Embed:
    card.set_footer(text=f"BlastBot v{__version__} • /help <lệnh> để xem chi tiết")
    return card


def _access_label(command: app_commands.Command[object, ..., object]) -> str:
    parent_permissions = command.parent.default_permissions if command.parent else None
    if command.default_permissions or parent_permissions:
        return "🔒 Quản trị"
    return "👤 Mọi thành viên"


def _usage(command: app_commands.Command[object, ..., object]) -> str:
    arguments = " ".join(
        f"<{parameter.display_name}>" if parameter.required else f"[{parameter.display_name}]"
        for parameter in command.parameters
    )
    return f"/{command.qualified_name}{f' {arguments}' if arguments else ''}"


def category_embed(
    category: str, commands_: list[app_commands.Command[object, ..., object]]
) -> discord.Embed:
    lines = [
        f"`/{command.qualified_name}` · {_access_label(command)}\n"
        f"↳ {command.description or 'Không có mô tả.'}"
        for command in commands_
    ]
    return _footer(
        discord.Embed(
            title=CATEGORY_NAMES.get(category, category),
            description="\n\n".join(lines),
            color=PRIMARY,
        )
    )


class HelpCategorySelect(discord.ui.Select):
    def __init__(
        self,
        categories: dict[str, list[app_commands.Command[object, ..., object]]],
    ) -> None:
        self.categories = categories
        super().__init__(
            placeholder="Chọn nhóm lệnh để xem chi tiết",
            options=[
                discord.SelectOption(
                    label=CATEGORY_NAMES.get(name, name),
                    value=name,
                    description=f"{len(items)} lệnh",
                )
                for name, items in sorted(categories.items())
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        category = self.values[0]
        await interaction.response.edit_message(
            embed=category_embed(category, self.categories[category]), view=self.view
        )


class HelpView(SafeView):
    def __init__(
        self,
        categories: dict[str, list[app_commands.Command[object, ..., object]]],
    ) -> None:
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect(categories))


class HelpCog(commands.Cog):
    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot

    def _commands(self) -> list[app_commands.Command[object, ..., object]]:
        commands_: list[app_commands.Command[object, ..., object]] = []
        for root in self.bot.tree.get_commands():
            if isinstance(root, app_commands.ContextMenu):
                continue
            if isinstance(root, app_commands.Group):
                commands_.extend(root.walk_commands())
            elif isinstance(root, app_commands.Command):
                commands_.append(root)
        return sorted(commands_, key=lambda item: item.qualified_name)

    def _categories(self) -> dict[str, list[app_commands.Command[object, ..., object]]]:
        categories: dict[str, list[app_commands.Command[object, ..., object]]] = defaultdict(list)
        for command in self._commands():
            categories[_category(command)].append(command)
        return dict(categories)

    @app_commands.command(name="help", description="Xem hướng dẫn và danh sách slash command")
    @app_commands.describe(command="Tên lệnh, ví dụ: reddit add hoặc warn")
    async def help(self, interaction: discord.Interaction, command: str | None = None) -> None:
        commands_ = self._commands()
        if command:
            normalized = command.strip().lstrip("/").casefold()
            selected = next(
                (item for item in commands_ if item.qualified_name.casefold() == normalized),
                None,
            )
            if selected is None:
                await interaction.response.send_message(
                    embed=error(
                        "Không tìm thấy lệnh",
                        f"Không có slash command `/{normalized}`. Chọn gợi ý khi nhập `/help`.",
                    ),
                    ephemeral=True,
                )
                return
            card = info(f"/{selected.qualified_name}", selected.description or "Không có mô tả.")
            card.add_field(
                name="Cách dùng",
                value=f"`{_usage(selected)}`",
                inline=False,
            )
            card.add_field(
                name="Quyền truy cập",
                value=_access_label(selected),
                inline=False,
            )
            await interaction.response.send_message(embed=_footer(card), ephemeral=True)
            return

        categories = self._categories()
        total = sum(len(items) for items in categories.values())
        summary = "\n".join(
            f"{CATEGORY_NAMES.get(name, name)} · **{len(items)}**"
            for name, items in sorted(categories.items())
        )
        card = discord.Embed(
            title="👋 Trung tâm trợ giúp BlastBot",
            description=(
                f"Có **{total} slash command**. Chọn một nhóm bên dưới để xem mô tả từng lệnh. "
                "Lệnh quản trị chỉ chạy khi bạn và bot có đủ quyền.\n\n"
                f"{summary}\n\n"
                "**Context menu:** nhấp phải vào user hoặc tin nhắn → **Apps** để xem avatar, "
                "bookmark hoặc gửi báo cáo."
            ),
            color=PRIMARY,
        )
        await interaction.response.send_message(
            embed=_footer(card), view=HelpView(categories), ephemeral=True
        )

    @help.autocomplete("command")
    async def help_autocomplete(
        self, _: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        needle = current.casefold().strip().lstrip("/")
        return [
            app_commands.Choice(name=f"/{item.qualified_name}", value=item.qualified_name)
            for item in self._commands()
            if needle in item.qualified_name.casefold()
        ][:25]


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(HelpCog(bot))
