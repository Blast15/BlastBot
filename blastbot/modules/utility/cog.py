from __future__ import annotations

import math
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from blastbot.core.bot import BlastBot
from blastbot.core.errors import ValidationError
from blastbot.shared.embeds import info, success
from blastbot.shared.permissions import require_guild_permissions
from blastbot.shared.validation import require_text


def build_poll(question: str, options: str, hours: int, multiple: bool) -> discord.Poll:
    question = require_text(question, maximum=300)
    answers = [answer.strip() for answer in options.split("|")]
    if not 2 <= len(answers) <= 10 or any(not answer or len(answer) > 55 for answer in answers):
        raise ValidationError("invalid poll answers",
                              "Nhập 2–10 lựa chọn cách nhau bằng |, mỗi lựa chọn 1–55 ký tự.")
    if len({answer.casefold() for answer in answers}) != len(answers):
        raise ValidationError("duplicate poll answers", "Các lựa chọn không được trùng nhau.")
    if not 1 <= hours <= 168:
        raise ValidationError("invalid poll duration", "Thời lượng phải từ 1 đến 168 giờ.")
    poll = discord.Poll(question=question, duration=timedelta(hours=hours), multiple=multiple)
    for answer in answers:
        poll.add_answer(text=answer)
    return poll


class UtilityCog(commands.Cog):
    def __init__(self, bot: BlastBot):
        self.bot = bot

    @app_commands.command(name="ping", description="Xem độ trễ kết nối Discord của bot")
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency
        text = f"**{latency * 1000:.0f} ms**" if math.isfinite(latency) else "Đang kết nối…"
        await interaction.response.send_message(embed=info("🏓 Pong", f"Gateway: {text}"),
                                                ephemeral=True)

    @app_commands.command(
        name="botinfo", description="Xem phiên bản và thời gian hoạt động của bot"
    )
    async def botinfo(self, interaction: discord.Interaction):
        card = info(
            "🤖 BlastBot",
            f"Hoạt động từ {discord.utils.format_dt(self.bot.started_at, 'R')}\n"
            f"Server: **{len(self.bot.guilds)}**\n"
            f"Module đang bật: **{len(self.bot.extensions)}**",
        )
        await interaction.response.send_message(embed=card, ephemeral=True)

    @app_commands.command(name="serverinfo", description="Xem thông tin và thống kê server")
    @app_commands.guild_only()
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            raise app_commands.NoPrivateMessage()
        card = info(f"🏠 {guild.name}", f"ID: `{guild.id}`\nChủ server: <@{guild.owner_id}>\n"
                    f"Ngày tạo: {discord.utils.format_dt(guild.created_at, 'D')}")
        card.add_field(name="Thành viên", value=str(guild.member_count or len(guild.members)))
        card.add_field(name="Kênh", value=str(len(guild.channels)))
        card.add_field(name="Role", value=str(len(guild.roles) - 1))
        card.add_field(
            name="Boost",
            value=f"Cấp {guild.premium_tier} · {guild.premium_subscription_count}",
        )
        if guild.icon:
            card.set_thumbnail(url=guild.icon.url)
        await interaction.response.send_message(embed=card, ephemeral=True)

    @app_commands.command(name="poll", description="Tạo bình chọn Discord với 2–10 lựa chọn")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: (i.guild_id, i.user.id))
    @app_commands.checks.bot_has_permissions(send_messages=True, send_polls=True)
    @require_guild_permissions(manage_messages=True)
    @app_commands.describe(question="Câu hỏi (tối đa 300 ký tự)",
                           options="Các lựa chọn cách nhau bằng |, ví dụ: Thứ bảy | Chủ nhật",
                           hours="Thời lượng 1–168 giờ, mặc định 24",
                           multiple="Cho phép chọn nhiều đáp án")
    async def poll(self, interaction: discord.Interaction, question: str, options: str,
                   hours: app_commands.Range[int, 1, 168] = 24, multiple: bool = False):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            raise ValidationError(
                "poll needs text channel", "Hãy tạo bình chọn trong kênh văn bản."
            )
        poll = build_poll(question, options, hours, multiple)
        await interaction.response.defer(ephemeral=True)
        message = await channel.send(poll=poll, allowed_mentions=discord.AllowedMentions.none())
        await interaction.followup.send(embed=success("Đã tạo bình chọn",
            f"[Mở bình chọn]({message.jump_url}) · Kết thúc sau **{hours} giờ**.\n"
            "Discord lưu phiếu bầu ngay cả khi bot khởi động lại."), ephemeral=True)


async def setup(bot: BlastBot):
    await bot.add_cog(UtilityCog(bot))
