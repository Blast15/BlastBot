"""Standalone ticket moderation slash commands."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import success_embed

from .helpers import is_ticket_staff
from .views import apply_claim_perms

logger = logging.getLogger("BlastBot.Tickets.Cmds")


class TicketCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add", description="➕ Thêm người dùng vào ticket")
    @app_commands.describe(member="Thành viên cần thêm")
    @app_commands.guild_only()
    async def add_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(
                "❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True
            )
        if not isinstance(
            interaction.user, discord.Member
        ) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message(
                "❌ Chỉ staff mới có quyền thêm người dùng.", ephemeral=True
            )

        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )
        await self.bot.db.add_ticket_member(interaction.channel.id, member.id)
        await interaction.response.send_message(
            embed=success_embed("Đã thêm", f"Đã thêm {member.mention} vào ticket.")
        )

    @app_commands.command(name="remove", description="➖ Gỡ người dùng khỏi ticket")
    @app_commands.describe(member="Thành viên cần gỡ")
    @app_commands.guild_only()
    async def remove_cmd(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(
                "❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True
            )
        if not isinstance(
            interaction.user, discord.Member
        ) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message(
                "❌ Chỉ staff mới có quyền gỡ người dùng.", ephemeral=True
            )
        if member.id == ticket["owner_id"]:
            return await interaction.response.send_message(
                "❌ Không thể gỡ chủ ticket.", ephemeral=True
            )

        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.set_permissions(member, overwrite=None)
        await self.bot.db.remove_ticket_member(interaction.channel.id, member.id)
        await interaction.response.send_message(
            embed=success_embed("Đã gỡ", f"Đã gỡ {member.mention} khỏi ticket.")
        )

    @app_commands.command(name="rename", description="✏️ Đổi tên channel ticket")
    @app_commands.describe(name="Tên mới cho channel")
    @app_commands.guild_only()
    async def rename_cmd(self, interaction: discord.Interaction, name: str):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(
                "❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True
            )
        if not isinstance(
            interaction.user, discord.Member
        ) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message(
                "❌ Chỉ staff mới được đổi tên ticket.", ephemeral=True
            )

        clean_name = name.lower().replace(" ", "-")[:100]
        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.edit(name=clean_name)
        await interaction.response.send_message(
            embed=success_embed(
                "Đã đổi tên", f"Channel đã đổi tên thành `{clean_name}`."
            )
        )

    @app_commands.command(
        name="transfer", description="🔄 Chuyển giao ticket cho staff khác"
    )
    @app_commands.describe(staff="Staff cần chuyển giao")
    @app_commands.guild_only()
    async def transfer_cmd(
        self, interaction: discord.Interaction, staff: discord.Member
    ):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(
                "❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True
            )
        if not isinstance(
            interaction.user, discord.Member
        ) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message(
                "❌ Chỉ staff mới chuyển giao được ticket.", ephemeral=True
            )
        if not await is_ticket_staff(self.bot, staff):
            return await interaction.response.send_message(
                "❌ Người nhận chuyển giao phải là staff.", ephemeral=True
            )

        await self.bot.db.set_claim(interaction.channel.id, staff.id)
        if isinstance(interaction.channel, discord.TextChannel):
            await apply_claim_perms(self.bot, interaction.channel, ticket, staff)
        await interaction.response.send_message(
            embed=success_embed(
                "Đã chuyển giao", f"Đã chuyển giao ticket cho {staff.mention}."
            )
        )


async def setup(bot):
    await bot.add_cog(TicketCommands(bot))
