from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from blastbot.core.bot import BlastBot
from blastbot.shared.embeds import error, info, success
from blastbot.modules.roles.ui import RoleMenuSetupView
from blastbot.shared.permissions import require_guild_permissions, validate_role_manage


class RolesCog(commands.Cog):
    rolemenu = app_commands.Group(
        name="rolemenu",
        description="Quản lý self-assign role menu",
        default_permissions=discord.Permissions(manage_roles=True),
        guild_only=True,
    )
    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot

    @app_commands.command(name="roleinfo", description="Xem thông tin chi tiết về một role")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role) -> None:
        perms = role.permissions
        names = []
        for attr, label in (
            ("administrator", "👑 Administrator"),
            ("manage_guild", "⚙️ Manage Server"),
            ("manage_roles", "🎭 Manage Roles"),
            ("manage_channels", "📝 Manage Channels"),
            ("kick_members", "👢 Kick Members"),
            ("ban_members", "🔨 Ban Members"),
            ("moderate_members", "⏱️ Timeout Members"),
        ):
            if getattr(perms, attr):
                names.append(label)
        card = info(f"🎭 Role: {role.name}", f"**ID:** `{role.id}`")
        card.color = role.color if role.color.value else discord.Color.blurple()
        card.add_field(
            name="📊 Thông tin",
            value=(
                f"**Members:** {len(role.members)}\n"
                f"**Position:** {role.position}\n"
                f"**Mentionable:** {'✅' if role.mentionable else '❌'}\n"
                f"**Hoisted:** {'✅' if role.hoist else '❌'}\n"
                f"**Managed:** {'✅' if role.managed else '❌'}"
            ),
        )
        if names:
            card.add_field(name="🔑 Key Permissions", value="\n".join(names[:10]), inline=False)
        card.set_footer(text=f"Created: {role.created_at:%d/%m/%Y %H:%M}")
        await interaction.response.send_message(embed=card)

    async def _change_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        *,
        add: bool,
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        problem = validate_role_manage(interaction.guild, interaction.user, role)
        if problem:
            await interaction.response.send_message(embed=error("Không thể quản lý role", problem), ephemeral=True)
            return
        if add and role in member.roles:
            await interaction.response.send_message(
                embed=error("Không thay đổi", f"{member.mention} đã có {role.mention}."), ephemeral=True
            )
            return
        if not add and role not in member.roles:
            await interaction.response.send_message(
                embed=error("Không thay đổi", f"{member.mention} không có {role.mention}."), ephemeral=True
            )
            return
        if add:
            await member.add_roles(role, reason=f"Role added by {interaction.user}")
            text = f"Đã thêm {role.mention} cho {member.mention}."
        else:
            await member.remove_roles(role, reason=f"Role removed by {interaction.user}")
            text = f"Đã xóa {role.mention} khỏi {member.mention}."
        await interaction.response.send_message(embed=success("Hoàn tất", text))

    @app_commands.command(name="roleadd", description="Thêm role cho một member")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @require_guild_permissions(manage_roles=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def roleadd(
        self, interaction: discord.Interaction, member: discord.Member, role: discord.Role
    ) -> None:
        await self._change_role(interaction, member, role, add=True)

    @app_commands.command(name="roleremove", description="Xóa role khỏi một member")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @require_guild_permissions(manage_roles=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def roleremove(
        self, interaction: discord.Interaction, member: discord.Member, role: discord.Role
    ) -> None:
        await self._change_role(interaction, member, role, add=False)

    @rolemenu.command(name="create", description="Tạo self-assign role menu bằng Role Select")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Toggle nhiều role", value="toggle"),
            app_commands.Choice(name="Chỉ một role", value="single"),
        ]
    )
    @require_guild_permissions(manage_roles=True)
    async def rolemenu_create(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        mode: app_commands.Choice[str],
    ) -> None:
        await interaction.response.send_message(
            embed=info("Chọn role", "Chọn các role mà member được phép tự gán."),
            view=RoleMenuSetupView(
                self.bot,
                channel=channel,
                title=title,
                description=description,
                mode=mode.value,
            ),
            ephemeral=True,
        )

    @rolemenu.command(name="list", description="Liệt kê self-assign role menu")
    @require_guild_permissions(manage_roles=True)
    async def rolemenu_list(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        menus = await self.bot.app.role_menus.list_for_guild(interaction.guild_id)
        lines = [
            f"`{item.message_id}` · <#{item.channel_id}> · {len(item.role_ids)} role · `{item.mode}`"
            for item in menus
        ]
        await interaction.response.send_message(
            embed=info("Role menus", "\n".join(lines) or "Chưa có role menu."), ephemeral=True
        )

    @rolemenu.command(name="delete", description="Ngừng quản lý một self-assign role menu")
    @require_guild_permissions(manage_roles=True)
    async def rolemenu_delete(self, interaction: discord.Interaction, message_id: str) -> None:
        if interaction.guild_id is None:
            return
        try:
            parsed = int(message_id)
        except ValueError:
            await interaction.response.send_message(
                embed=error("Message ID không hợp lệ", "Message ID phải là số."), ephemeral=True
            )
            return
        deleted = await self.bot.app.role_menus_repo.delete(interaction.guild_id, parsed)
        await interaction.response.send_message(
            embed=success("Role menu", "Đã xóa cấu hình." if deleted else "Không tìm thấy cấu hình."),
            ephemeral=True,
        )


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(RolesCog(bot))
