from __future__ import annotations

from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from blastbot import __version__
from blastbot.core.bot import BlastBot
from blastbot.shared.embeds import info
from blastbot.shared.ui import SafeView


def _qualified_name(command: app_commands.Command | app_commands.Group) -> str:
    return command.qualified_name


class HelpCategorySelect(discord.ui.Select):
    def __init__(self, bot: BlastBot, categories: dict[str, list[str]]) -> None:
        self.bot = bot
        self.categories = categories
        options = [
            discord.SelectOption(label=name, value=name, description=f"{len(items)} command")
            for name, items in sorted(categories.items())[:25]
        ]
        super().__init__(placeholder="Chọn nhóm lệnh", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        category = self.values[0]
        lines = self.categories.get(category, [])
        await interaction.response.edit_message(
            embed=info(f"Help · {category}", "\n".join(f"`/{name}`" for name in lines)),
            view=self.view,
        )


class HelpView(SafeView):
    def __init__(self, bot: BlastBot, categories: dict[str, list[str]]) -> None:
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect(bot, categories))


class HelpCog(commands.Cog):
    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot

    def _commands(self) -> list[app_commands.Command | app_commands.Group]:
        return sorted(self.bot.tree.get_commands(), key=_qualified_name)

    @app_commands.command(name="help", description="Xem danh sách lệnh hoặc chi tiết một lệnh")
    @app_commands.describe(command="Tên lệnh, ví dụ: ticket limit")
    async def help(self, interaction: discord.Interaction, command: str | None = None) -> None:
        commands_ = self._commands()
        if command:
            normalized = command.strip().lstrip("/").lower()
            for item in commands_:
                if item.qualified_name.lower() == normalized:
                    description = item.description or "Không có mô tả."
                    await interaction.response.send_message(
                        embed=info(f"/{item.qualified_name}", description), ephemeral=True
                    )
                    return
                if isinstance(item, app_commands.Group):
                    for child in item.walk_commands():
                        if child.qualified_name.lower() == normalized:
                            await interaction.response.send_message(
                                embed=info(f"/{child.qualified_name}", child.description or "Không có mô tả."),
                                ephemeral=True,
                            )
                            return
            await interaction.response.send_message(
                embed=info("Không tìm thấy", f"Không tìm thấy command `/{normalized}`."), ephemeral=True
            )
            return

        categories: dict[str, list[str]] = defaultdict(list)
        for item in commands_:
            binding = getattr(item, "binding", None)
            category = binding.__class__.__name__.removesuffix("Cog") if binding is not None else "Other"
            if isinstance(item, app_commands.Group):
                categories[category].extend(child.qualified_name for child in item.walk_commands())
            else:
                categories[category].append(item.qualified_name)

        total = sum(len(items) for items in categories.values())
        summary = "\n".join(
            f"**{name}** · {len(items)} lệnh" for name, items in sorted(categories.items())
        )
        card = info("BlastBot Help", f"Có **{total}** lệnh.\n\n{summary}")
        card.set_footer(text=f"BlastBot v{__version__}")
        await interaction.response.send_message(
            embed=card,
            view=HelpView(self.bot, categories),
            ephemeral=True,
        )

    @help.autocomplete("command")
    async def help_autocomplete(
        self, _: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        needle = current.lower().strip()
        names: list[str] = []
        for item in self._commands():
            if isinstance(item, app_commands.Group):
                names.extend(child.qualified_name for child in item.walk_commands())
            else:
                names.append(item.qualified_name)
        return [
            app_commands.Choice(name=f"/{name}", value=name)
            for name in names
            if needle in name.lower()
        ][:25]


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(HelpCog(bot))
