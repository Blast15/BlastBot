"""Standalone ticket moderation slash commands."""

import discord
from discord import app_commands
from discord.ext import commands
import logging

from utils.embeds import success_embed, error_embed, create_embed
from utils.constants import COLORS
from .helpers import is_ticket_staff
from .views import open_ticket, perform_close, apply_claim_perms, ConfirmCloseView, CloseRequestView

logger = logging.getLogger('BlastBot.Tickets.Cmds')


class TicketCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="open", description="🎫 Mở ticket hỗ trợ mới")
    @app_commands.guild_only()
    async def open_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        panel = None
        if interaction.guild:
            panels = await self.bot.db.list_panels(interaction.guild.id)
            if panels:
                panel = await self.bot.db.get_panel(panels[0]['panel_id'])
        await open_ticket(self.bot, interaction, panel=panel)

    @app_commands.command(name="close", description="🔒 Đóng ticket hiện tại")
    @app_commands.describe(reason="Lý do đóng ticket")
    @app_commands.guild_only()
    async def close_cmd(self, interaction: discord.Interaction, reason: str | None = None):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member):
            return
        if interaction.user.id != ticket['owner_id'] and not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Bạn không có quyền đóng ticket này.", ephemeral=True)

        await interaction.response.send_message(
            embed=create_embed(title="Xác nhận đóng ticket",
                               description=f"Channel sẽ bị xóa sau khi lưu transcript.\n**Lý do:** {reason or 'Không có'}",
                               color=COLORS['warning']),
            view=ConfirmCloseView(self.bot))

    @app_commands.command(name="closerequest", description="📩 Gửi yêu cầu đóng ticket cho người tạo")
    @app_commands.describe(reason="Lý do đề nghị đóng")
    @app_commands.guild_only()
    async def closerequest_cmd(self, interaction: discord.Interaction, reason: str | None = None):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới dùng được lệnh này.", ephemeral=True)

        owner = interaction.guild.get_member(ticket['owner_id']) if interaction.guild else None
        owner_mention = owner.mention if owner else f"<@{ticket['owner_id']}>"

        embed = create_embed(
            title="📩 Yêu cầu đóng ticket",
            description=f"{interaction.user.mention} đề nghị đóng ticket này.\n**Lý do:** {reason or 'Không có lý do'}",
            color=COLORS['info']
        )
        view = CloseRequestView(self.bot, owner_id=ticket['owner_id'], reason=reason)
        await interaction.response.send_message(content=owner_mention, embed=embed, view=view)

    @app_commands.command(name="add", description="➕ Thêm người dùng vào ticket")
    @app_commands.describe(member="Thành viên cần thêm")
    @app_commands.guild_only()
    async def add_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới có quyền thêm người dùng.", ephemeral=True)

        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.set_permissions(
                member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True
            )
        await interaction.response.send_message(embed=success_embed("Đã thêm", f"Đã thêm {member.mention} vào ticket."))

    @app_commands.command(name="remove", description="➖ Gỡ người dùng khỏi ticket")
    @app_commands.describe(member="Thành viên cần gỡ")
    @app_commands.guild_only()
    async def remove_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới có quyền gỡ người dùng.", ephemeral=True)
        if member.id == ticket['owner_id']:
            return await interaction.response.send_message("❌ Không thể gỡ chủ ticket.", ephemeral=True)

        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(embed=success_embed("Đã gỡ", f"Đã gỡ {member.mention} khỏi ticket."))

    @app_commands.command(name="rename", description="✏️ Đổi tên channel ticket")
    @app_commands.describe(name="Tên mới cho channel")
    @app_commands.guild_only()
    async def rename_cmd(self, interaction: discord.Interaction, name: str):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới được đổi tên ticket.", ephemeral=True)

        clean_name = name.lower().replace(" ", "-")[:100]
        if isinstance(interaction.channel, discord.TextChannel):
            await interaction.channel.edit(name=clean_name)
        await interaction.response.send_message(embed=success_embed("Đã đổi tên", f"Channel đã đổi tên thành `{clean_name}`."))

    @app_commands.command(name="claim", description="🙋 Nhận xử lý ticket")
    @app_commands.guild_only()
    async def claim_cmd(self, interaction: discord.Interaction):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới claim được ticket.", ephemeral=True)
        if ticket['claimed_by']:
            return await interaction.response.send_message(f"❌ Ticket đã được <@{ticket['claimed_by']}> nhận xử lý.", ephemeral=True)

        await self.bot.db.set_claim(interaction.channel.id, interaction.user.id)
        if isinstance(interaction.channel, discord.TextChannel):
            await apply_claim_perms(self.bot, interaction.channel, ticket, interaction.user)
        await interaction.response.send_message(embed=success_embed("Đã nhận xử lý", f"{interaction.user.mention} phụ trách ticket này."))

    @app_commands.command(name="unclaim", description="🙌 Bỏ nhận xử lý ticket")
    @app_commands.guild_only()
    async def unclaim_cmd(self, interaction: discord.Interaction):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới dùng được lệnh này.", ephemeral=True)
        if not ticket['claimed_by']:
            return await interaction.response.send_message("❌ Ticket chưa được ai nhận xử lý.", ephemeral=True)
        if ticket['claimed_by'] != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Bạn không phải người đã claim ticket này.", ephemeral=True)

        await self.bot.db.set_claim(interaction.channel.id, None)

        if isinstance(interaction.channel, discord.TextChannel) and interaction.guild:
            staff = await self.bot.db.get_staff(interaction.guild.id)
            for e in staff:
                if e['is_role']:
                    role = interaction.guild.get_role(e['entity_id'])
                    if role:
                        try:
                            await interaction.channel.set_permissions(role, view_channel=True, send_messages=True)
                        except discord.HTTPException:
                            pass

        await interaction.response.send_message(embed=success_embed("Đã bỏ nhận", "Ticket hiện khả dụng cho staff khác nhận xử lý."))

    @app_commands.command(name="transfer", description="🔄 Chuyển giao ticket cho staff khác")
    @app_commands.describe(staff="Staff cần chuyển giao")
    @app_commands.guild_only()
    async def transfer_cmd(self, interaction: discord.Interaction, staff: discord.Member):
        if interaction.channel is None:
            return
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Lệnh này chỉ dùng trong channel ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(self.bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới chuyển giao được ticket.", ephemeral=True)
        if not await is_ticket_staff(self.bot, staff):
            return await interaction.response.send_message("❌ Người nhận chuyển giao phải là staff.", ephemeral=True)

        await self.bot.db.set_claim(interaction.channel.id, staff.id)
        if isinstance(interaction.channel, discord.TextChannel):
            await apply_claim_perms(self.bot, interaction.channel, ticket, staff)
        await interaction.response.send_message(embed=success_embed("Đã chuyển giao", f"Đã chuyển giao ticket cho {staff.mention}."))


async def setup(bot):
    await bot.add_cog(TicketCommands(bot))
