"""Auto-message: gửi tin nhắn lặp lại theo chu kỳ."""

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.moderation.base import require_guild_permissions
from utils.constants import AUTOMATION_CONFIG, COLORS
from utils.embeds import create_embed, error_embed, success_embed
from utils.error_handler import (
    ValidationError,
    validate_number_range,
    validate_string_length,
)

logger = logging.getLogger("BlastBot.Automation.AutoMessage")


class AutoMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_message_loop.start()

    def cog_unload(self):
        self.auto_message_loop.cancel()

    automsg = app_commands.Group(
        name="automsg",
        description="Quản lý tin nhắn tự động lặp lại",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    @automsg.command(name="add", description="Thêm auto-message")
    @app_commands.describe(
        channel="Channel gửi tin",
        content="Nội dung tin nhắn",
        interval="Chu kỳ (phút)",
        use_embed="Gửi dạng embed?",
    )
    @require_guild_permissions(manage_guild=True)
    async def add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        content: str,
        interval: int,
        use_embed: bool = False,
    ):
        if interaction.guild is None:
            return
        try:
            content = validate_string_length(
                content, min_len=1, max_len=4000 if use_embed else 2000
            )
            validate_number_range(
                interval,
                AUTOMATION_CONFIG["min_interval_minutes"],
                AUTOMATION_CONFIG["max_interval_minutes"],
                "Chu kỳ (phút)",
            )
        except ValidationError as e:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", e.user_message), ephemeral=True
            )

        existing = await self.bot.db.list_auto_messages(interaction.guild.id)
        if len(existing) >= AUTOMATION_CONFIG["max_auto_messages"]:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Lỗi",
                    f"Đã đạt giới hạn {AUTOMATION_CONFIG['max_auto_messages']} auto-message.",
                ),
                ephemeral=True,
            )

        aid = await self.bot.db.create_auto_message(
            interaction.guild.id, channel.id, content, interval, use_embed
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Đã thêm",
                f"Auto-message `{aid}` sẽ gửi vào {channel.mention} mỗi **{interval} phút**.",
            ),
            ephemeral=True,
        )

    @automsg.command(name="list", description="Xem danh sách auto-message")
    @require_guild_permissions(manage_guild=True)
    async def list_cmd(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        items = await self.bot.db.list_auto_messages(interaction.guild.id)
        if not items:
            return await interaction.response.send_message(
                embed=create_embed(
                    title="Auto-messages",
                    description="Chưa có cái nào.",
                    color=COLORS["info"],
                ),
                ephemeral=True,
            )
        lines = []
        for m in items:
            status = "🟢" if m["enabled"] else "🔴"
            preview = (
                (m["content"][:40] + "…") if len(m["content"]) > 40 else m["content"]
            )
            lines.append(
                f"{status} `{m['id']}` — <#{m['channel_id']}> mỗi "
                f"{m['interval_minutes']}p: {preview}"
            )
        await interaction.response.send_message(
            embed=create_embed(
                title="📨 Auto-messages",
                description="\n".join(lines),
                color=COLORS["info"],
            ),
            ephemeral=True,
        )

    @automsg.command(name="delete", description="Xóa auto-message")
    @app_commands.describe(auto_id="ID auto-message")
    @require_guild_permissions(manage_guild=True)
    async def delete(self, interaction: discord.Interaction, auto_id: int):
        if interaction.guild is None:
            return
        ok = await self.bot.db.delete_auto_message(interaction.guild.id, auto_id)
        embed = (
            success_embed("Đã xóa", f"Đã xóa auto-message `{auto_id}`.")
            if ok
            else error_embed("Lỗi", f"Không tìm thấy auto-message `{auto_id}`.")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automsg.command(name="toggle", description="Bật/tắt một auto-message")
    @app_commands.describe(auto_id="ID auto-message", enabled="Bật?")
    @require_guild_permissions(manage_guild=True)
    async def toggle(
        self, interaction: discord.Interaction, auto_id: int, enabled: bool
    ):
        if interaction.guild is None:
            return
        ok = await self.bot.db.toggle_auto_message(
            interaction.guild.id, auto_id, enabled
        )
        embed = (
            success_embed(
                "Đã cập nhật",
                f"Auto-message `{auto_id}` đã {'bật' if enabled else 'tắt'}.",
            )
            if ok
            else error_embed("Lỗi", f"Không tìm thấy auto-message `{auto_id}`.")
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tasks.loop(minutes=AUTOMATION_CONFIG["auto_message_check_minutes"])
    async def auto_message_loop(self):
        db = getattr(self.bot, "db", None)
        if db is None:
            return
        try:
            due = await db.get_due_auto_messages()
            for m in due:
                guild = self.bot.get_guild(m["guild_id"])
                if not guild:
                    continue
                channel = guild.get_channel(m["channel_id"])
                if not isinstance(channel, discord.TextChannel):
                    logger.warning(
                        "Auto-message %s bị vô hiệu hóa vì channel %s không còn hợp lệ.",
                        m["id"],
                        m["channel_id"],
                    )
                    await db.toggle_auto_message(m["guild_id"], m["id"], False)
                    continue
                try:
                    allowed_mentions = discord.AllowedMentions(
                        everyone=False, roles=False, users=True
                    )
                    if m["use_embed"]:
                        await channel.send(
                            embed=create_embed(
                                description=m["content"], color=COLORS["primary"]
                            ),
                            allowed_mentions=allowed_mentions,
                        )
                    else:
                        await channel.send(
                            m["content"], allowed_mentions=allowed_mentions
                        )
                    await db.mark_auto_message_sent(m["id"])
                except discord.HTTPException as e:
                    logger.warning(f"Auto-message {m['id']} lỗi gửi: {e}")
        except Exception as e:
            logger.error(f"Lỗi auto_message_loop: {e}", exc_info=True)

    @auto_message_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(AutoMessage(bot))
