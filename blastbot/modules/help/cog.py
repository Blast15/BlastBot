from __future__ import annotations

from collections import defaultdict
from contextlib import suppress

import discord
from discord import app_commands
from discord.ext import commands

from blastbot import __version__
from blastbot.core.bot import BlastBot
from blastbot.shared.embeds import PRIMARY, info
from blastbot.shared.ui import SafeView

CATEGORY_NAMES = {
    "Automation": "⚡ Tự động hóa",
    "Configuration": "⚙️ Cấu hình",
    "ContextMenus": "👤 Thành viên",
    "Help": "📚 Trợ giúp",
    "Moderation": "🛡️ Kiểm duyệt",
    "Reddit": "📰 Reddit",
    "Roles": "🎭 Role",
    "Utility": "🧰 Tiện ích",
}
PAGE_SIZE = 8
EXAMPLES = {
    "help": "/help command:bình chọn",
    "poll": "/poll question:Đi chơi ngày nào? options:Thứ bảy | Chủ nhật hours:24",
    "slowmode": "/slowmode seconds:10 (hoặc seconds:0 để tắt)",
    "userinfo": "/userinfo member:@thành_viên",
    "avatar": "/avatar member:@thành_viên",
    "reddit add": "/reddit add subreddit:python channel:#reddit",
    "config logchannel": "/config logchannel channel:#mod-log",
}


def _category(command: app_commands.Command) -> str:
    binding = command.binding
    return binding.__class__.__name__.removesuffix("Cog") if binding is not None else "Khác"


def _footer(card: discord.Embed) -> discord.Embed:
    card.set_footer(text=f"BlastBot v{__version__} • Chỉ bạn thấy help • /help để mở lại")
    return card


def _permissions(command: app_commands.Command) -> discord.Permissions | None:
    root = command.root_parent or command
    return root.default_permissions


def _access_label(command: app_commands.Command) -> str:
    permissions = _permissions(command)
    if permissions is not None:
        names = [name for name, enabled in permissions if enabled]
        return "🔒 " + (", ".join(names) if names else "Quản trị viên")
    return "👤 Mọi thành viên"


def _usage(command: app_commands.Command) -> str:
    arguments = " ".join(
        f"<{p.display_name}>" if p.required else f"[{p.display_name}]"
        for p in command.parameters
    )
    return f"/{command.qualified_name}{f' {arguments}' if arguments else ''}"


def category_embed(category: str, commands_: list[app_commands.Command], page: int = 0):
    pages = max(1, (len(commands_) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    lines = [
        f"**`/{command.qualified_name}`**\n{command.description}\n{_access_label(command)}"
        for command in commands_[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    ]
    return _footer(discord.Embed(
        title=CATEGORY_NAMES.get(category, category),
        description=(f"Trang **{page + 1}/{pages}** · {len(commands_)} lệnh\n"
                     "Chọn một lệnh bên dưới để xem cách dùng.\n\n" + "\n\n".join(lines)),
        color=PRIMARY,
    ))


def command_embed(command: app_commands.Command) -> discord.Embed:
    card = info(f"/{command.qualified_name}", command.description)
    card.add_field(name="Cách dùng", value=f"`{_usage(command)}`"[:1024], inline=False)
    card.add_field(name="Quyền mặc định", value=_access_label(command), inline=False)
    lines = []
    for parameter in command.parameters:
        detail = parameter.description if parameter.description != "…" else parameter.type.name
        limits = []
        if parameter.min_value is not None:
            limits.append(f"tối thiểu {parameter.min_value}")
        if parameter.max_value is not None:
            limits.append(f"tối đa {parameter.max_value}")
        if not parameter.required and parameter.default is not None:
            limits.append(f"mặc định: {parameter.default}")
        if parameter.choices:
            limits.append(" / ".join(str(choice.value) for choice in parameter.choices))
        suffix = f" ({', '.join(limits)})" if limits else ""
        lines.append(f"• **{parameter.display_name}** · "
                     f"{'Bắt buộc' if parameter.required else 'Tùy chọn'}: {detail}{suffix}")
    if lines:
        # A command may have 25 parameters; keep Discord's embed limits even for long choices.
        text = "\n".join(lines)
        card.add_field(name="Tham số", value=text[:1021] + "…" if len(text) > 1024 else text,
                       inline=False)
    example = EXAMPLES.get(command.qualified_name)
    if example:
        card.add_field(name="Ví dụ", value=f"`{example}`", inline=False)
    card.add_field(
        name="Mẹo sử dụng",
        value="`<...>` bắt buộc · `[...]` tùy chọn. Gõ tên lệnh trong ô chat rồi chọn "
              "tham số Discord gợi ý. Quyền thực tế còn phụ thuộc kênh, cấu hình server "
              "và thứ bậc role của bạn/bot.",
        inline=False,
    )
    return _footer(card)


class HelpSelect(discord.ui.Select):
    def __init__(self, *, options, placeholder: str, kind: str, row: int):
        self.kind = kind
        super().__init__(options=options, placeholder=placeholder, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        if self.kind == "category":
            view.category = self.values[0]
            view.page = 0
            view.selected = None
        else:
            view.selected = next(c for c in view.items if c.qualified_name == self.values[0])
        view.rebuild()
        await interaction.response.edit_message(embed=view.embed(), view=view)


class HelpView(SafeView):
    def __init__(self, categories: dict[str, list[app_commands.Command]], *, owner_id: int,
                 menus: tuple[str, ...] = (), selected: app_commands.Command | None = None,
                 search: str | None = None):
        super().__init__(timeout=180)
        self.categories = categories
        self.owner_id = owner_id
        self.menus = menus
        self.category = _category(selected) if selected else None
        self.selected = selected
        self.search = search
        self.page = self.items.index(selected) // PAGE_SIZE if selected else 0
        self.message: discord.InteractionMessage | None = None
        self.rebuild()

    @property
    def items(self):
        return self.categories.get(self.category, [])

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("Dùng /help để mở hướng dẫn của riêng bạn.",
                                                ephemeral=True)
        return False

    def embed(self):
        if self.selected:
            return command_embed(self.selected)
        if self.category:
            return category_embed(self.category, self.items, self.page)
        total = sum(len(items) for items in self.categories.values())
        summary = "\n".join(f"{CATEGORY_NAMES.get(name, name)} · **{len(items)}**"
                            for name, items in sorted(self.categories.items()))
        card = info("📚 Trung tâm trợ giúp BlastBot",
                    f"**{total} lệnh** đang bật · Chọn nhóm → chọn lệnh → xem cách dùng.\n\n"
                    + (summary or "Không có lệnh phù hợp. Thử /help với từ khóa khác."))
        if self.search:
            card.add_field(name="Kết quả tìm kiếm", value=discord.utils.escape_markdown(
                self.search[:100]), inline=False)
        else:
            names = {c.qualified_name for items in self.categories.values() for c in items}
            suggestions = [("serverinfo", "Xem server"), ("poll", "Tạo bình chọn"),
                           ("config logchannel", "Cài kênh log"),
                           ("greeting welcome", "Cài lời chào"),
                           ("rolemenu create", "Tạo menu role")]
            quick = [f"`/{name}` — {label}" for name, label in suggestions if name in names]
            if quick:
                card.add_field(name="Bắt đầu nhanh", value="\n".join(quick), inline=False)
        if self.menus:
            card.add_field(name="Menu chuột phải → Apps", value=" · ".join(self.menus)[:1024],
                           inline=False)
        card.add_field(name="Tìm nhanh", value="`/help command:từ khóa` tìm trong tên và mô tả. "
                       "Help hiển thị quyền mặc định; lệnh quản trị vẫn kiểm tra quyền khi chạy.",
                       inline=False)
        return _footer(card)

    def rebuild(self):
        self.clear_items()
        if self.categories:
            self.add_item(HelpSelect(
                options=[discord.SelectOption(label=CATEGORY_NAMES.get(name, name), value=name,
                         description=f"{len(items)} lệnh", default=name == self.category)
                         for name, items in sorted(self.categories.items())],
                placeholder="1. Chọn nhóm lệnh", kind="category", row=0))
        if self.items:
            self.add_item(HelpSelect(
                options=[discord.SelectOption(label=f"/{c.qualified_name}", value=c.qualified_name,
                         description=c.description[:100])
                         for c in self.items[self.page * PAGE_SIZE:(self.page + 1) * PAGE_SIZE]],
                placeholder="2. Chọn lệnh để xem cách dùng", kind="command", row=1))
        self.previous.disabled = not self.category or self.page == 0
        self.next_page.disabled = (
            not self.category or (self.page + 1) * PAGE_SIZE >= len(self.items)
        )
        self.back.disabled = self.selected is None
        for button in (self.home, self.back, self.previous, self.next_page):
            self.add_item(button)

    async def refresh(self, interaction):
        self.rebuild()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Trang chủ", emoji="🏠", row=2)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.category = self.selected = None
        self.page = 0
        await self.refresh(interaction)

    @discord.ui.button(label="Danh sách", row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected = None
        await self.refresh(interaction)

    @discord.ui.button(label="Trước", row=2)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        self.selected = None
        await self.refresh(interaction)

    @discord.ui.button(label="Sau", row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(max(0, (len(self.items) - 1) // PAGE_SIZE), self.page + 1)
        self.selected = None
        await self.refresh(interaction)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            with suppress(discord.HTTPException):
                await self.message.edit(view=self)


class HelpCog(commands.Cog):
    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot

    def _commands(self) -> list[app_commands.Command]:
        result = []
        for root in self.bot.tree.get_commands():
            if isinstance(root, app_commands.Group):
                result.extend(
                    c for c in root.walk_commands() if isinstance(c, app_commands.Command)
                )
            elif isinstance(root, app_commands.Command):
                result.append(root)
        return sorted(result, key=lambda item: item.qualified_name)

    def _categories(self) -> dict[str, list[app_commands.Command]]:
        result = defaultdict(list)
        for command in self._commands():
            result[_category(command)].append(command)
        return dict(result)

    @app_commands.command(name="help", description="Tìm lệnh, xem hướng dẫn và quyền cần có")
    @app_commands.describe(command="Tên lệnh hoặc từ khóa, ví dụ: reddit add, role, bình chọn")
    async def help(self, interaction: discord.Interaction, command: str | None = None) -> None:
        needle = " ".join((command or "").strip().lstrip("/").casefold().split())
        commands_ = self._commands()
        selected = next((c for c in commands_ if c.qualified_name.casefold() == needle), None)
        categories = self._categories()
        if needle and selected is None:
            categories = {name: [c for c in items if needle in
                          f"{c.qualified_name} {c.description}".casefold()]
                          for name, items in categories.items()}
            categories = {name: items for name, items in categories.items() if items}
        menus = tuple(c.name for c in self.bot.tree.get_commands()
                      if isinstance(c, app_commands.ContextMenu))
        view = HelpView(categories, owner_id=interaction.user.id, menus=menus,
                        selected=selected, search=needle if needle and not selected else None)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)
        view.message = await interaction.original_response()

    @help.autocomplete("command")
    async def help_autocomplete(self, _: discord.Interaction, current: str):
        needle = " ".join(current.casefold().strip().lstrip("/").split())
        return [app_commands.Choice(name=f"/{c.qualified_name}", value=c.qualified_name)
                for c in self._commands()
                if needle in f"{c.qualified_name} {c.description}".casefold()][:25]


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(HelpCog(bot))
