from __future__ import annotations

import logging

import discord

from blastbot.core.bot import BlastBot
from blastbot.core.errors import PermissionDeniedError, ResourceNotFoundError
from blastbot.modules.tickets.permissions import is_blacklisted, is_ticket_staff, ticket_overwrites
from blastbot.modules.tickets.service import PanelData
from blastbot.modules.tickets.transcript import build_transcript_file
from blastbot.shared.embeds import error, info, success
from blastbot.shared.ui import SafeView

logger = logging.getLogger(__name__)


def _safe_channel_name(number: int, owner: discord.Member) -> str:
    base = "".join(ch for ch in owner.display_name.lower().replace(" ", "-") if ch.isalnum() or ch == "-")
    return f"ticket-{number:04d}-{base[:28] or owner.id}"


async def _resolve_panel_from_interaction(
    bot: BlastBot, interaction: discord.Interaction
) -> PanelData | None:
    if interaction.guild_id is None or interaction.message is None:
        return None
    return await bot.app.tickets.panel_for_message(interaction.guild_id, interaction.message.id)


async def open_ticket(bot: BlastBot, interaction: discord.Interaction) -> None:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            embed=error("Không khả dụng", "Ticket chỉ có thể mở trong server."), ephemeral=True
        )
        return

    panel = await _resolve_panel_from_interaction(bot, interaction)
    if panel is None:
        await interaction.response.send_message(
            embed=error("Panel không hợp lệ", "Panel này không còn tồn tại trong cấu hình."),
            ephemeral=True,
        )
        return

    blacklist = await bot.app.tickets_repo.blacklist(interaction.guild.id)
    if is_blacklisted(interaction.user, blacklist):
        await interaction.response.send_message(
            embed=error("Không thể mở ticket", "Bạn đang nằm trong blacklist của hệ thống ticket."),
            ephemeral=True,
        )
        return

    category = interaction.guild.get_channel(panel.category_id)
    if not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message(
            embed=error("Category không hợp lệ", "Category của panel đã bị xóa hoặc thay đổi."),
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    reservation = await bot.app.tickets.reserve(interaction.guild.id, interaction.user.id, panel.panel_id)
    channel: discord.TextChannel | None = None
    try:
        bot_member = interaction.guild.me
        if bot_member is None:
            raise ResourceNotFoundError("bot member unavailable", "Không thể xác định bot member.")
        staff = await bot.app.tickets_repo.staff(interaction.guild.id)
        channel = await interaction.guild.create_text_channel(
            _safe_channel_name(reservation.number, interaction.user),
            category=category,
            overwrites=ticket_overwrites(interaction.guild, interaction.user, bot_member, staff),
            topic=f"BlastBot ticket #{reservation.number} · owner={interaction.user.id}",
            reason=f"Ticket #{reservation.number} opened by {interaction.user}",
        )
        await bot.app.tickets.finalize(reservation.id, channel.id)
    except Exception:
        # This rollback boundary must cover any channel-creation/finalization failure;
        # cleanup is attempted and the original exception is always re-raised.
        await bot.app.tickets.abandon(reservation.id)
        if channel is not None:
            try:
                await channel.delete(reason="Ticket creation rollback")
            except discord.HTTPException:
                logger.exception("Could not rollback orphan ticket channel", extra={"channel_id": channel.id})
        raise

    mentions: list[str] = [interaction.user.mention]
    for role_id in panel.mention_on_open:
        role = interaction.guild.get_role(role_id)
        if role is not None:
            mentions.append(role.mention)
    welcome = panel.welcome_message or "Hãy mô tả vấn đề của bạn. Staff sẽ hỗ trợ sớm nhất có thể."
    await channel.send(
        " ".join(mentions),
        embed=info(f"Ticket #{reservation.number}", welcome),
        view=TicketControlView(bot),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
    )
    await interaction.followup.send(
        embed=success("Đã mở ticket", f"Ticket của bạn: {channel.mention}"), ephemeral=True
    )


async def perform_close(
    bot: BlastBot,
    channel: discord.TextChannel,
    *,
    actor: discord.Member,
    reason: str,
    system: bool = False,
) -> bool:
    ticket = await bot.app.tickets_repo.get_ticket_by_channel(channel.id)
    if ticket is None or not ticket.open:
        return False

    staff = await bot.app.tickets_repo.staff(channel.guild.id)
    if not system and actor.id != ticket.owner_id and not is_ticket_staff(actor, staff):
        raise PermissionDeniedError("ticket close denied", "Bạn không có quyền đóng ticket này.")

    closed = await bot.app.tickets_repo.close_ticket(channel.id, reason)
    if not closed:
        return False

    settings = await bot.app.tickets.settings(channel.guild.id)
    if settings.transcript_channel_id:
        destination = channel.guild.get_channel(settings.transcript_channel_id)
        if isinstance(destination, discord.TextChannel):
            try:
                transcript = await build_transcript_file(
                    channel,
                    message_limit=bot.app.settings.transcript_message_limit,
                )
                await destination.send(
                    embed=info(
                        f"Transcript ticket #{ticket.number}",
                        f"Owner: <@{ticket.owner_id}>\nClosed by: {actor.mention}\nReason: {reason}",
                    ),
                    file=transcript,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                logger.exception(
                    "Failed to upload ticket transcript",
                    extra={"guild_id": channel.guild.id, "channel_id": channel.id},
                )

    try:
        await channel.delete(reason=f"Ticket closed by {actor}: {reason}")
    except discord.HTTPException:
        logger.exception(
            "Ticket marked closed but channel deletion failed",
            extra={"guild_id": channel.guild.id, "channel_id": channel.id},
        )
    return True


class TicketPanelView(SafeView):
    def __init__(self, bot: BlastBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Tạo ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="ticket:panel:create",
    )
    async def create_ticket(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await open_ticket(self.bot, interaction)


class ConfirmCloseView(SafeView):
    def __init__(self, bot: BlastBot, requester_id: int) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.requester_id = requester_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.requester_id

    @discord.ui.button(label="Đóng ticket", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer(ephemeral=True)
        await perform_close(self.bot, interaction.channel, actor=interaction.user, reason="Đóng thủ công")
        self.stop()

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Đã hủy thao tác đóng ticket.", view=None)
        self.stop()


class TicketControlView(SafeView):
    def __init__(self, bot: BlastBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.secondary,
        emoji="🙋",
        custom_id="ticket:control:claim",
    )
    async def claim(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel) or not isinstance(interaction.user, discord.Member):
            return
        ticket = await self.bot.app.tickets_repo.get_ticket_by_channel(interaction.channel.id)
        if ticket is None or not ticket.open:
            await interaction.response.send_message(
                embed=error("Không phải ticket", "Channel này không phải ticket đang mở."), ephemeral=True
            )
            return
        staff = await self.bot.app.tickets_repo.staff(interaction.guild_id or 0)
        if not is_ticket_staff(interaction.user, staff):
            await interaction.response.send_message(
                embed=error("Không đủ quyền", "Chỉ ticket staff mới có thể claim."), ephemeral=True
            )
            return
        await self.bot.app.tickets_repo.set_claim(interaction.channel.id, interaction.user.id)
        settings = await self.bot.app.tickets.settings(interaction.guild_id or 0)
        if settings.claim_mode == "reply_only":
            for item in staff:
                target = interaction.guild.get_role(item.entity_id) if item.is_role and interaction.guild else (
                    interaction.guild.get_member(item.entity_id) if interaction.guild else None
                )
                if target is not None and target != interaction.user:
                    try:
                        await interaction.channel.set_permissions(target, send_messages=False)
                    except discord.HTTPException:
                        logger.exception("Failed to enforce reply_only claim mode")
            await interaction.channel.set_permissions(
                interaction.user, view_channel=True, send_messages=True, read_message_history=True
            )
        await interaction.response.send_message(
            embed=success("Đã claim", f"{interaction.user.mention} đã nhận ticket này."),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @discord.ui.button(
        label="Đóng",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket:control:close",
    )
    async def close(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        await interaction.response.send_message(
            "Xác nhận đóng ticket?",
            view=ConfirmCloseView(self.bot, interaction.user.id),
            ephemeral=True,
        )


class CloseRequestView(SafeView):
    """Persistent staff approval view used by /closerequest."""

    def __init__(self, bot: BlastBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    async def _staff_check(self, interaction: discord.Interaction) -> discord.Member:
        if not isinstance(interaction.user, discord.Member) or interaction.guild_id is None:
            raise PermissionDeniedError("not a guild member", "Thao tác này chỉ dùng trong server.")
        staff = await self.bot.app.tickets_repo.staff(interaction.guild_id)
        if not is_ticket_staff(interaction.user, staff):
            raise PermissionDeniedError("not ticket staff", "Chỉ ticket staff mới có thể xử lý yêu cầu.")
        return interaction.user

    @discord.ui.button(
        label="Chấp nhận",
        style=discord.ButtonStyle.success,
        custom_id="ticket:close_request:accept",
    )
    async def accept(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        actor = await self._staff_check(interaction)
        await interaction.response.defer()
        await perform_close(self.bot, interaction.channel, actor=actor, reason="Staff chấp nhận yêu cầu đóng")

    @discord.ui.button(
        label="Từ chối",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket:close_request:deny",
    )
    async def deny(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        actor = await self._staff_check(interaction)
        await interaction.response.edit_message(
            embed=info("Yêu cầu đóng bị từ chối", f"Được xử lý bởi {actor.mention}."),
            view=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
