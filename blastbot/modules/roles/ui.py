from __future__ import annotations

import discord

from blastbot.core.bot import BlastBot
from blastbot.shared.embeds import error, success
from blastbot.shared.permissions import validate_role_manage
from blastbot.shared.ui import SafeView


class RoleMenuSelect(discord.ui.Select):
    def __init__(
        self,
        bot: BlastBot,
        roles: tuple[discord.Role, ...] | None = None,
        *,
        mode: str = "toggle",
    ) -> None:
        self.bot = bot
        options = [
            discord.SelectOption(label=role.name[:100], value=str(role.id), emoji="🎭")
            for role in (roles or ())
        ]
        if not options:
            options = [discord.SelectOption(label="Role", value="0")]
        super().__init__(
            placeholder="Chọn role",
            min_values=1,
            max_values=1 if mode == "single" else max(1, len(options)),
            options=options,
            custom_id="roles:menu:select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if (
            interaction.message is None
            or interaction.guild is None
            or not isinstance(interaction.user, discord.Member)
        ):
            return
        menu = await self.bot.app.role_menus.get(interaction.message.id)
        allowed = set(menu.role_ids)
        selected = [int(value) for value in self.values if int(value) in allowed]
        if not selected:
            await interaction.response.send_message(
                embed=error(
                    "Role không hợp lệ",
                    "Role menu đã thay đổi hoặc role không còn tồn tại.",
                ),
                ephemeral=True,
            )
            return

        manageable: list[discord.Role] = []
        bot_member = interaction.guild.me
        if bot_member is None:
            return
        for role_id in selected:
            role = interaction.guild.get_role(role_id)
            if role is None or role.managed or role >= bot_member.top_role:
                continue
            manageable.append(role)

        if not manageable:
            await interaction.response.send_message(
                embed=error(
                    "Không thể cấp role", "Bot không thể quản lý các role đã chọn."
                ),
                ephemeral=True,
            )
            return

        if menu.mode == "single":
            chosen = manageable[0]
            remove_roles = [
                role
                for role in interaction.user.roles
                if role.id in allowed and role != chosen
            ]
            if remove_roles:
                await interaction.user.remove_roles(
                    *remove_roles, reason="Role menu single-select"
                )
            if chosen not in interaction.user.roles:
                await interaction.user.add_roles(
                    chosen, reason="Role menu single-select"
                )
            text = f"Role hiện tại: {chosen.mention}."
        else:
            to_add = [role for role in manageable if role not in interaction.user.roles]
            to_remove = [role for role in manageable if role in interaction.user.roles]
            if to_add:
                await interaction.user.add_roles(*to_add, reason="Role menu toggle")
            if to_remove:
                await interaction.user.remove_roles(
                    *to_remove, reason="Role menu toggle"
                )
            added = ", ".join(role.mention for role in to_add) or "không có"
            removed = ", ".join(role.mention for role in to_remove) or "không có"
            text = f"Đã thêm: {added}\nĐã gỡ: {removed}"

        await interaction.response.send_message(
            embed=success("Đã cập nhật role", text),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class RoleMenuView(SafeView):
    def __init__(
        self,
        bot: BlastBot,
        roles: tuple[discord.Role, ...] | None = None,
        *,
        mode: str = "toggle",
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(RoleMenuSelect(bot, roles, mode=mode))


class RoleMenuSetupSelect(discord.ui.RoleSelect):
    def __init__(
        self,
        bot: BlastBot,
        *,
        channel: discord.TextChannel,
        title: str,
        description: str,
        mode: str,
    ) -> None:
        super().__init__(placeholder="Chọn 1-25 role", min_values=1, max_values=25)
        self.bot = bot
        self.channel = channel
        self.title = title
        self.description = description
        self.mode = mode

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            return
        bot_member = interaction.guild.me
        if bot_member is None:
            return
        roles = tuple(role for role in self.values if isinstance(role, discord.Role))
        for role in roles:
            problem = validate_role_manage(interaction.guild, interaction.user, role)
            if problem:
                await interaction.response.send_message(
                    embed=error(
                        "Role không thể self-assign", f"{role.mention}: {problem}"
                    ),
                    ephemeral=True,
                )
                return
        card = discord.Embed(
            title=self.title[:256],
            description=self.description[:4000],
            color=discord.Color.blurple(),
        )
        message = await self.channel.send(
            embed=card, view=RoleMenuView(self.bot, roles, mode=self.mode)
        )
        await self.bot.app.role_menus.create(
            message_id=message.id,
            guild_id=interaction.guild.id,
            channel_id=self.channel.id,
            role_ids=tuple(role.id for role in roles),
            mode=self.mode,
        )
        await interaction.response.edit_message(
            embed=success(
                "Đã tạo role menu", f"Role menu đã gửi tại {message.jump_url}."
            ),
            view=None,
        )
        if self.view is not None:
            self.view.stop()


class RoleMenuSetupView(SafeView):
    def __init__(
        self,
        bot: BlastBot,
        *,
        channel: discord.TextChannel,
        title: str,
        description: str,
        mode: str,
    ) -> None:
        super().__init__(timeout=180)
        self.add_item(
            RoleMenuSetupSelect(
                bot,
                channel=channel,
                title=title,
                description=description,
                mode=mode,
            )
        )
