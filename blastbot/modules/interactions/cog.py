from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from blastbot.core.bot import BlastBot
from blastbot.modules.moderation.ui import ReportModal
from blastbot.shared.embeds import info, success


class ContextMenusCog(commands.Cog):
    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot
        self._menus = (
            app_commands.ContextMenu(name="Thông tin User", callback=self.user_info),
            app_commands.ContextMenu(name="Báo cáo User", callback=self.report_user),
            app_commands.ContextMenu(name="Xem Avatar", callback=self.avatar),
            app_commands.ContextMenu(name="Báo cáo Message", callback=self.report_message),
            app_commands.ContextMenu(name="Bookmark Message", callback=self.bookmark_message),
        )
        for menu in self._menus:
            self.bot.tree.add_command(menu)

    def cog_unload(self) -> None:
        for menu in self._menus:
            self.bot.tree.remove_command(menu.name, type=menu.type)

    async def user_info(self, interaction: discord.Interaction, member: discord.Member) -> None:
        roles = [role.mention for role in reversed(member.roles[1:])]
        joined_at = (
            discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "Không rõ"
        )
        card = info(
            f"Thông tin {member}",
            f"ID: `{member.id}`\n"
            f"Tạo tài khoản: {discord.utils.format_dt(member.created_at, 'R')}\n"
            f"Tham gia server: {joined_at}\n"
            f"Roles: {' '.join(roles[:15]) if roles else 'Không có'}",
        )
        card.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=card, ephemeral=True)

    async def report_user(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.send_modal(
            ReportModal(self.bot.app.moderation, target_id=member.id, target_type="user")
        )

    async def avatar(self, interaction: discord.Interaction, member: discord.Member) -> None:
        card = info(f"Avatar · {member}", None)
        card.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=card, ephemeral=True)

    async def report_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        await interaction.response.send_modal(
            ReportModal(
                self.bot.app.moderation,
                target_id=message.id,
                target_type="message",
                message_context={
                    "author": message.author.id,
                    "jump_url": message.jump_url,
                    "content": message.content[:1000],
                },
            )
        )

    async def bookmark_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        card = info(
            "Bookmark",
            f"Tác giả: {message.author.mention}\n"
            f"Channel: {message.channel.mention}\n"
            f"[Đi tới message]({message.jump_url})\n\n"
            f"{message.content[:1500] or '*Không có nội dung text*'}",
        )
        try:
            await interaction.user.send(embed=card, allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=info("Không thể gửi DM", "Hãy bật DM từ thành viên server rồi thử lại."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success("Đã bookmark", "Đã gửi message vào DM của bạn."),
            ephemeral=True,
        )


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(ContextMenusCog(bot))
