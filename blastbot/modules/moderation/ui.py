from __future__ import annotations

import logging

import discord

from blastbot.modules.moderation.service import ModerationService
from blastbot.shared.embeds import error, success
from blastbot.shared.ui import SafeModal, SafeView
from blastbot.shared.validation import require_text

logger = logging.getLogger(__name__)


class ReportModal(SafeModal, title="Báo cáo người dùng/tin nhắn"):
    reason = discord.ui.TextInput(label="Lý do báo cáo", required=True, max_length=100)
    details = discord.ui.TextInput(
        label="Chi tiết", required=True, max_length=1000, style=discord.TextStyle.paragraph
    )

    def __init__(
        self,
        service: ModerationService,
        *,
        target_id: int,
        target_type: str,
        message_context: dict[str, int | str] | None = None,
    ) -> None:
        super().__init__()
        self.service = service
        self.target_id = target_id
        self.target_type = target_type
        self.message_context = message_context or {}

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = require_text(str(self.reason.value), maximum=100)
        details = require_text(str(self.details.value), maximum=1000)
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=error("Không thể gửi báo cáo", "Báo cáo chỉ dùng trong server."),
                ephemeral=True,
            )
            return

        channel_id = await self.service.repository.get_log_channel_id(interaction.guild.id)
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                embed=error(
                    "Chưa cấu hình kênh báo cáo",
                    "Quản trị viên cần dùng `/config logchannel` trước khi nhận báo cáo.",
                ),
                ephemeral=True,
            )
            return

        lines = [
            f"**Người báo cáo:** {interaction.user.mention} (`{interaction.user.id}`)",
            f"**Target ID:** `{self.target_id}`",
        ]
        if author := self.message_context.get("author"):
            lines.append(f"**Tác giả tin nhắn:** <@{author}> (`{author}`)")
        if jump := self.message_context.get("jump_url"):
            lines.append(f"**Link tin nhắn:** [Đi đến tin nhắn]({jump})")
        card = discord.Embed(
            title=f"Báo cáo mới - {self.target_type.title()}",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        card.add_field(name="Lý do", value=reason, inline=False)
        card.add_field(name="Chi tiết", value=details, inline=False)
        if content := self.message_context.get("content"):
            card.add_field(name="Nội dung tin nhắn", value=str(content), inline=False)
        try:
            await channel.send(embed=card, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            logger.exception("Failed to send report", extra={"guild_id": interaction.guild.id})
            await interaction.response.send_message(
                embed=error("Không thể gửi báo cáo", "Bot không thể gửi vào kênh báo cáo."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success("Báo cáo đã gửi", "Đội ngũ quản lý sẽ xem xét báo cáo."),
            ephemeral=True,
        )


class ConfirmView(SafeView):
    def __init__(self, user_id: int, *, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.value: bool | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Bạn không thể sử dụng nút này.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Xác nhận", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.value = False
        await interaction.response.defer()
        self.stop()
