from __future__ import annotations

import logging
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from blastbot.core.bot import BlastBot
from blastbot.database.models import Ticket
from blastbot.modules.tickets.permissions import is_ticket_staff
from blastbot.modules.tickets.ui import CloseRequestView, TicketPanelView, perform_close
from blastbot.shared.embeds import error, info, success
from blastbot.shared.permissions import require_guild_permissions

logger = logging.getLogger(__name__)


class TicketCog(commands.Cog):
    ticket = app_commands.Group(
        name="ticket",
        description="Cấu hình ticket",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )
    panel = app_commands.Group(
        name="panel",
        description="Quản lý ticket panel",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )
    managetags = app_commands.Group(
        name="managetags",
        description="Quản lý quick tags của ticket",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot
        self.autoclose_loop.start()

    def cog_unload(self) -> None:
        self.autoclose_loop.cancel()

    async def _require_ticket_staff(self, interaction: discord.Interaction) -> discord.Member | None:
        if not isinstance(interaction.user, discord.Member) or interaction.guild_id is None:
            return None
        staff = await self.bot.app.tickets_repo.staff(interaction.guild_id)
        if is_ticket_staff(interaction.user, staff):
            return interaction.user
        await interaction.response.send_message(
            embed=error("Không đủ quyền", "Bạn không phải ticket staff."), ephemeral=True
        )
        return None

    async def _current_ticket(self, interaction: discord.Interaction) -> Ticket | None:
        if not isinstance(interaction.channel, discord.TextChannel):
            return None
        return await self.bot.app.tickets_repo.get_ticket_by_channel(interaction.channel.id)

    @ticket.command(name="transcripts", description="Đặt channel lưu transcript")
    @require_guild_permissions(manage_guild=True)
    async def transcripts(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.tickets.set_transcript_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(
            embed=success("Đã cập nhật", f"Transcript sẽ được gửi vào {channel.mention}."),
            ephemeral=True,
        )

    @ticket.command(name="limit", description="Đặt số ticket tối đa mỗi thành viên")
    @require_guild_permissions(manage_guild=True)
    async def limit(
        self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 50]
    ) -> None:
        if interaction.guild_id is None:
            return
        value = await self.bot.app.tickets.set_limit(interaction.guild_id, int(amount))
        await interaction.response.send_message(
            embed=success("Đã cập nhật", f"Giới hạn ticket: **{value}**/thành viên."),
            ephemeral=True,
        )

    @ticket.command(name="autoclose", description="Tự đóng ticket không hoạt động sau N giờ (0 = tắt)")
    @require_guild_permissions(manage_guild=True)
    async def autoclose(
        self, interaction: discord.Interaction, hours: app_commands.Range[int, 0, 720]
    ) -> None:
        if interaction.guild_id is None:
            return
        value = await self.bot.app.tickets.set_autoclose(interaction.guild_id, int(hours))
        message = "Autoclose đã tắt." if value == 0 else f"Ticket sẽ tự đóng sau **{value} giờ** không hoạt động."
        await interaction.response.send_message(embed=success("Đã cập nhật", message), ephemeral=True)

    @ticket.command(name="claimmode", description="Chọn hành vi sau khi staff claim ticket")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Chỉ người claim được trả lời", value="reply_only"),
            app_commands.Choice(name="Tất cả staff vẫn trả lời", value="view_all"),
        ]
    )
    @require_guild_permissions(manage_guild=True)
    async def claimmode(
        self, interaction: discord.Interaction, mode: app_commands.Choice[str]
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.tickets.set_claim_mode(interaction.guild_id, mode.value)
        await interaction.response.send_message(
            embed=success("Đã cập nhật", f"Claim mode: `{mode.value}`."), ephemeral=True
        )

    @ticket.command(name="addsupport", description="Thêm user hoặc role vào ticket staff")
    @require_guild_permissions(manage_guild=True)
    async def addsupport(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        role: discord.Role | None = None,
    ) -> None:
        if interaction.guild_id is None or (member is None) == (role is None):
            await interaction.response.send_message(
                embed=error("Input không hợp lệ", "Chọn đúng một member hoặc một role."), ephemeral=True
            )
            return
        target = member or role
        assert target is not None
        await self.bot.app.tickets_repo.add_staff(
            interaction.guild_id, target.id, isinstance(target, discord.Role), "support"
        )
        await interaction.response.send_message(
            embed=success("Đã thêm support", target.mention), ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @ticket.command(name="removesupport", description="Xóa user hoặc role khỏi ticket staff")
    @require_guild_permissions(manage_guild=True)
    async def removesupport(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        role: discord.Role | None = None,
    ) -> None:
        if interaction.guild_id is None or (member is None) == (role is None):
            await interaction.response.send_message(
                embed=error("Input không hợp lệ", "Chọn đúng một member hoặc một role."), ephemeral=True
            )
            return
        target = member or role
        assert target is not None
        await self.bot.app.tickets_repo.remove_staff(interaction.guild_id, target.id, "support")
        await interaction.response.send_message(
            embed=success("Đã xóa support", target.mention), ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @ticket.command(name="viewstaff", description="Xem danh sách ticket staff")
    @require_guild_permissions(manage_guild=True)
    async def viewstaff(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        staff = await self.bot.app.tickets_repo.staff(interaction.guild_id)
        text = "\n".join(
            f"{'Role' if item.is_role else 'User'} · <@{'&' if item.is_role else ''}{item.entity_id}> · `{item.type}`"
            for item in staff
        ) or "Chưa có ticket staff."
        await interaction.response.send_message(embed=info("Ticket staff", text), ephemeral=True)

    @ticket.command(name="blacklist", description="Bật/tắt blacklist ticket cho member hoặc role")
    @require_guild_permissions(manage_guild=True)
    async def blacklist(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
        role: discord.Role | None = None,
    ) -> None:
        if interaction.guild_id is None or (member is None) == (role is None):
            await interaction.response.send_message(
                embed=error("Input không hợp lệ", "Chọn đúng một member hoặc một role."), ephemeral=True
            )
            return
        target = member or role
        assert target is not None
        enabled = await self.bot.app.tickets_repo.toggle_blacklist(
            interaction.guild_id, target.id, isinstance(target, discord.Role)
        )
        await interaction.response.send_message(
            embed=success(
                "Đã cập nhật blacklist",
                f"{target.mention}: {'đã chặn' if enabled else 'đã gỡ chặn'}.",
            ),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @panel.command(name="create", description="Tạo cấu hình ticket panel")
    @require_guild_permissions(manage_guild=True)
    async def panel_create(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        title: str,
        content: str,
        button_label: str = "Tạo ticket",
        mention_role: discord.Role | None = None,
    ) -> None:
        if interaction.guild_id is None:
            return
        panel_id = await self.bot.app.tickets.create_panel(
            guild_id=interaction.guild_id,
            category_id=category.id,
            title=title,
            content=content,
            button_label=button_label,
            mention_role_id=mention_role.id if mention_role else None,
        )
        await interaction.response.send_message(
            embed=success("Đã tạo panel", f"Panel ID: `{panel_id}`."), ephemeral=True
        )

    @panel.command(name="send", description="Gửi ticket panel ra channel")
    @require_guild_permissions(manage_guild=True)
    async def panel_send(
        self, interaction: discord.Interaction, panel_id: int, channel: discord.TextChannel
    ) -> None:
        if interaction.guild_id is None:
            return
        panel = await self.bot.app.tickets.get_panel(panel_id, interaction.guild_id)
        embed = discord.Embed(title=panel.title, description=panel.content, color=panel.color)
        message = await channel.send(embed=embed, view=TicketPanelView(self.bot))
        await self.bot.app.tickets_repo.set_panel_message(
            interaction.guild_id, panel_id, channel.id, message.id
        )
        await interaction.response.send_message(
            embed=success("Đã gửi panel", f"Panel `{panel_id}` đã gửi tại {message.jump_url}."),
            ephemeral=True,
        )

    @panel.command(name="list", description="Liệt kê ticket panel")
    @require_guild_permissions(manage_guild=True)
    async def panel_list(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        panels = await self.bot.app.tickets.panels(interaction.guild_id)
        lines = [
            f"`{panel.panel_id}` · **{panel.title}** · category <#{panel.category_id}>"
            for panel in panels
        ]
        await interaction.response.send_message(
            embed=info("Ticket panels", "\n".join(lines) or "Chưa có panel."), ephemeral=True
        )

    @panel.command(name="edit", description="Sửa title/content/button label của panel")
    @require_guild_permissions(manage_guild=True)
    async def panel_edit(
        self,
        interaction: discord.Interaction,
        panel_id: int,
        title: str | None = None,
        content: str | None = None,
        button_label: str | None = None,
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.tickets.get_panel(panel_id, interaction.guild_id)
        changed = await self.bot.app.tickets.edit_panel(
            guild_id=interaction.guild_id,
            panel_id=panel_id,
            title=title,
            content=content,
            button_label=button_label,
        )
        await interaction.response.send_message(
            embed=success("Đã cập nhật", "Panel đã thay đổi." if changed else "Không có trường nào thay đổi."),
            ephemeral=True,
        )

    @panel.command(name="delete", description="Xóa ticket panel")
    @require_guild_permissions(manage_guild=True)
    async def panel_delete(self, interaction: discord.Interaction, panel_id: int) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.tickets.get_panel(panel_id, interaction.guild_id)
        await self.bot.app.tickets_repo.delete_panel(interaction.guild_id, panel_id)
        await interaction.response.send_message(
            embed=success("Đã xóa panel", f"Panel `{panel_id}` đã bị xóa."), ephemeral=True
        )

    @app_commands.command(name="add", description="Thêm thành viên vào ticket hiện tại")
    @app_commands.guild_only()
    async def add_member(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if await self._require_ticket_staff(interaction) is None or not isinstance(interaction.channel, discord.TextChannel):
            return
        ticket = await self._current_ticket(interaction)
        if ticket is None or not ticket.open:
            await interaction.response.send_message(embed=error("Không phải ticket", "Channel này không phải ticket đang mở."), ephemeral=True)
            return
        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await self.bot.app.tickets_repo.add_member(interaction.channel.id, member.id)
        await interaction.response.send_message(embed=success("Đã thêm", f"Đã thêm {member.mention} vào ticket."), allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="remove", description="Xóa thành viên khỏi ticket hiện tại")
    @app_commands.guild_only()
    async def remove_member(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if await self._require_ticket_staff(interaction) is None or not isinstance(interaction.channel, discord.TextChannel):
            return
        ticket = await self._current_ticket(interaction)
        if ticket is None or not ticket.open:
            await interaction.response.send_message(embed=error("Không phải ticket", "Channel này không phải ticket đang mở."), ephemeral=True)
            return
        await interaction.channel.set_permissions(member, overwrite=None)
        await self.bot.app.tickets_repo.remove_member(interaction.channel.id, member.id)
        await interaction.response.send_message(embed=success("Đã xóa", f"Đã xóa {member.mention} khỏi ticket."), allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="rename", description="Đổi tên ticket hiện tại")
    @app_commands.guild_only()
    async def rename(self, interaction: discord.Interaction, name: str) -> None:
        if await self._require_ticket_staff(interaction) is None or not isinstance(interaction.channel, discord.TextChannel):
            return
        if await self._current_ticket(interaction) is None:
            await interaction.response.send_message(embed=error("Không phải ticket", "Channel này không phải ticket."), ephemeral=True)
            return
        safe = "".join(ch for ch in name.lower().replace(" ", "-") if ch.isalnum() or ch == "-")[:90]
        if not safe:
            await interaction.response.send_message(embed=error("Tên không hợp lệ", "Tên ticket không được rỗng."), ephemeral=True)
            return
        await interaction.channel.edit(name=safe, reason=f"Ticket renamed by {interaction.user}")
        await interaction.response.send_message(embed=success("Đã đổi tên", f"Tên mới: `{safe}`."), ephemeral=True)

    @app_commands.command(name="transfer", description="Chuyển ownership của ticket")
    @app_commands.guild_only()
    async def transfer(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if await self._require_ticket_staff(interaction) is None or not isinstance(interaction.channel, discord.TextChannel):
            return
        ticket = await self._current_ticket(interaction)
        if ticket is None or not ticket.open:
            await interaction.response.send_message(embed=error("Không phải ticket", "Channel này không phải ticket đang mở."), ephemeral=True)
            return
        old_owner = interaction.guild.get_member(ticket.owner_id) if interaction.guild else None
        if old_owner:
            await interaction.channel.set_permissions(old_owner, overwrite=None)
        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await self.bot.app.tickets_repo.transfer_owner(interaction.channel.id, member.id)
        await interaction.response.send_message(embed=success("Đã transfer", f"Owner mới: {member.mention}."), allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="tag", description="Gửi quick tag trong ticket")
    @app_commands.guild_only()
    async def tag(self, interaction: discord.Interaction, tag_id: str) -> None:
        if interaction.guild_id is None or await self._require_ticket_staff(interaction) is None:
            return
        content = await self.bot.app.tickets.tag(interaction.guild_id, tag_id)
        if content is None:
            await interaction.response.send_message(embed=error("Không tìm thấy tag", f"Không có tag `{tag_id}`."), ephemeral=True)
            return
        await interaction.response.send_message(content, allowed_mentions=discord.AllowedMentions.none())

    @managetags.command(name="add", description="Tạo hoặc cập nhật quick tag")
    @require_guild_permissions(manage_guild=True)
    async def tags_add(self, interaction: discord.Interaction, tag_id: str, content: str) -> None:
        if interaction.guild_id is None:
            return
        normalized = await self.bot.app.tickets.add_tag(interaction.guild_id, tag_id, content)
        await interaction.response.send_message(embed=success("Đã lưu tag", f"Tag: `{normalized}`."), ephemeral=True)

    @managetags.command(name="delete", description="Xóa quick tag")
    @require_guild_permissions(manage_guild=True)
    async def tags_delete(self, interaction: discord.Interaction, tag_id: str) -> None:
        if interaction.guild_id is None:
            return
        deleted = await self.bot.app.tickets.delete_tag(interaction.guild_id, tag_id)
        await interaction.response.send_message(embed=success("Quick tags", "Đã xóa." if deleted else "Tag không tồn tại."), ephemeral=True)

    @managetags.command(name="list", description="Liệt kê quick tags")
    @require_guild_permissions(manage_guild=True)
    async def tags_list(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        tags = await self.bot.app.tickets_repo.tags(interaction.guild_id)
        await interaction.response.send_message(embed=info("Quick tags", "\n".join(f"`{tag}`" for tag in tags) or "Chưa có tag."), ephemeral=True)

    @app_commands.command(name="closerequest", description="Yêu cầu staff xác nhận đóng ticket")
    @app_commands.guild_only()
    async def close_request(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            return
        ticket = await self._current_ticket(interaction)
        if ticket is None or not ticket.open:
            await interaction.response.send_message(embed=error("Không phải ticket", "Channel này không phải ticket đang mở."), ephemeral=True)
            return
        if interaction.user.id != ticket.owner_id:
            await interaction.response.send_message(embed=error("Không đủ quyền", "Chỉ chủ ticket mới dùng lệnh này."), ephemeral=True)
            return
        await interaction.response.send_message(
            embed=info("Yêu cầu đóng ticket", f"{interaction.user.mention} yêu cầu đóng ticket. Staff hãy xác nhận."),
            view=CloseRequestView(self.bot),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="excludeautoclose", description="Loại ticket hiện tại khỏi autoclose")
    @app_commands.guild_only()
    async def exclude_autoclose(self, interaction: discord.Interaction) -> None:
        if await self._require_ticket_staff(interaction) is None or not isinstance(interaction.channel, discord.TextChannel):
            return
        ticket = await self._current_ticket(interaction)
        if ticket is None or not ticket.open:
            await interaction.response.send_message(embed=error("Không phải ticket", "Channel này không phải ticket đang mở."), ephemeral=True)
            return
        await self.bot.app.tickets_repo.exclude_autoclose(interaction.channel.id)
        await interaction.response.send_message(embed=success("Đã loại khỏi autoclose", "Ticket này sẽ không bị đóng do inactivity."), ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not isinstance(message.channel, discord.TextChannel):
            return
        ticket = await self.bot.app.tickets_repo.get_ticket_by_channel(message.channel.id)
        if ticket and ticket.open:
            await self.bot.app.tickets_repo.touch(message.channel.id)

    @tasks.loop(minutes=30.0)
    async def autoclose_loop(self) -> None:
        rows = await self.bot.app.tickets_repo.inactive_tickets(datetime.now(UTC))
        for ticket in rows:
            if ticket.channel_id is None:
                await self.bot.app.tickets_repo.abandon_reservation(ticket.id)
                continue
            guild = self.bot.get_guild(ticket.guild_id)
            channel = guild.get_channel(ticket.channel_id) if guild else None
            if not isinstance(channel, discord.TextChannel):
                await self.bot.app.tickets_repo.close_ticket(ticket.channel_id, "Channel không còn tồn tại")
                continue
            bot_member = guild.me if guild else None
            if bot_member is None:
                continue
            try:
                await perform_close(
                    self.bot, channel, actor=bot_member, reason="Autoclose do inactivity", system=True
                )
            except discord.HTTPException:
                logger.exception("Autoclose failed", extra={"guild_id": ticket.guild_id, "channel_id": ticket.channel_id})

    @autoclose_loop.error
    async def autoclose_loop_error(self, exception: BaseException) -> None:
        logger.exception(
            "Background task autoclose_loop failed",
            exc_info=exception,
            extra={"operation": "autoclose_loop", "error_type": type(exception).__name__},
        )

    @autoclose_loop.before_loop
    async def before_autoclose_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(TicketCog(bot))
