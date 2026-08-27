from __future__ import annotations

import logging

import discord

from blastbot.modules.feedback.service import FeedbackService
from blastbot.shared.embeds import error, success
from blastbot.shared.ui import SafeModal, SafeView

logger = logging.getLogger(__name__)


class SuggestionVotingView(SafeView):
    def __init__(self, service: FeedbackService) -> None:
        super().__init__(timeout=None)
        self.service = service

    def _labels(self, up: int, down: int) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "suggestion_upvote":
                    child.label = f"👍 {up}"
                elif child.custom_id == "suggestion_downvote":
                    child.label = f"👎 {down}"

    async def _vote(self, interaction: discord.Interaction, value: int) -> None:
        if interaction.message is None:
            await interaction.response.send_message(
                "Không xác định được suggestion.", ephemeral=True
            )
            return
        up, down = await self.service.vote(
            interaction.message.id, interaction.user.id, value
        )
        self._labels(up, down)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="👍 0", style=discord.ButtonStyle.success, custom_id="suggestion_upvote"
    )
    async def upvote(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._vote(interaction, 1)

    @discord.ui.button(
        label="👎 0", style=discord.ButtonStyle.danger, custom_id="suggestion_downvote"
    )
    async def downvote(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._vote(interaction, -1)


class SuggestionModal(SafeModal, title="Gửi góp ý"):
    suggestion = discord.ui.TextInput(
        label="Góp ý", required=True, max_length=1000, style=discord.TextStyle.paragraph
    )

    def __init__(self, service: FeedbackService) -> None:
        super().__init__()
        self.service = service

    async def on_submit(self, interaction: discord.Interaction) -> None:
        text = self.service.validate_suggestion(str(self.suggestion.value))
        card = discord.Embed(
            title="💡 Góp ý mới", description=text, color=discord.Color.blurple()
        )
        card.set_author(
            name=str(interaction.user), icon_url=interaction.user.display_avatar.url
        )
        card.set_footer(text=f"Suggestion ID: {interaction.id}")
        view = SuggestionVotingView(self.service)
        await interaction.response.send_message(embed=card, view=view)
        if interaction.guild_id is not None:
            message = await interaction.original_response()
            await self.service.register_suggestion(interaction.guild_id, message.id)


class ReportModal(SafeModal, title="Báo cáo người dùng/tin nhắn"):
    reason = discord.ui.TextInput(label="Lý do báo cáo", required=True, max_length=100)
    details = discord.ui.TextInput(
        label="Chi tiết",
        required=True,
        max_length=1000,
        style=discord.TextStyle.paragraph,
    )

    def __init__(
        self,
        service: FeedbackService,
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
        reason, details = self.service.validate_report(
            str(self.reason.value), str(self.details.value)
        )
        lines = [
            f"**Người báo cáo:** {interaction.user.mention} (`{interaction.user.id}`)",
            f"**Target ID:** `{self.target_id}`",
        ]
        if author := self.message_context.get("author"):
            lines.append(f"**Tác giả tin nhắn:** <@{author}> (`{author}`)")
        if jump := self.message_context.get("jump_url"):
            lines.append(f"**Link tin nhắn:** [Đi đến tin nhắn]({jump})")
        card = discord.Embed(
            title=f"📢 Báo cáo mới - {self.target_type.title()}",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        card.add_field(name="Lý do", value=reason, inline=False)
        card.add_field(name="Chi tiết", value=details, inline=False)
        if content := self.message_context.get("content"):
            card.add_field(name="Nội dung tin nhắn", value=str(content), inline=False)
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=error("Không thể gửi báo cáo", "Báo cáo chỉ dùng trong server."),
                ephemeral=True,
            )
            return
        channel_id = await self.service.repository.get_log_channel_id(
            interaction.guild.id
        )
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
        try:
            await channel.send(
                embed=card, allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.HTTPException:
            logger.exception("Failed to send report to log channel")
            await interaction.response.send_message(
                embed=error(
                    "Không thể gửi báo cáo",
                    "Bot không thể gửi vào kênh báo cáo. Hãy báo quản trị viên kiểm tra quyền.",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success(
                "Báo cáo đã gửi",
                "Cảm ơn bạn đã báo cáo. Đội ngũ quản lý sẽ xem xét sớm nhất.",
            ),
            ephemeral=True,
        )
