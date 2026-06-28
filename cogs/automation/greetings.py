"""Welcome & goodbye tự động."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.base import require_guild_permissions
from utils.constants import AUTOMATION_CONFIG, COLORS
from utils.embeds import create_embed, error_embed, success_embed
from utils.error_handler import ValidationError, validate_string_length
from utils.placeholders import render_placeholders

logger = logging.getLogger("BlastBot.Automation.Greetings")


class Greetings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    greeting = app_commands.Group(
        name="greeting",
        description="Cấu hình lời chào/tạm biệt",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    async def _send_greeting(self, member: discord.Member, kind: str):
        db = getattr(self.bot, "db", None)
        if db is None:
            return
        cfg = await db.get_greeting(member.guild.id, kind)
        if not cfg["enabled"] or not cfg["channel_id"]:
            return
        channel = member.guild.get_channel(cfg["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return

        message = render_placeholders(
            cfg["message"]
            or (
                "Chào mừng {user_mention} đến với **{server}**! 👋"
                if kind == "welcome"
                else "Tạm biệt **{user_name}**, hẹn gặp lại! 👋"
            ),
            member,
        )
        try:
            if cfg["use_embed"]:
                embed = create_embed(
                    title=render_placeholders(cfg["title"] or "", member) or None,
                    description=message,
                    color=cfg["color"] or COLORS["primary"],
                    thumbnail=member.display_avatar.url,
                )
                await channel.send(embed=embed)
            else:
                await channel.send(message)
        except discord.HTTPException as e:
            logger.warning(f"Không gửi được {kind} cho {member}: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            await self._send_greeting(member, "welcome")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not member.bot:
            await self._send_greeting(member, "goodbye")

    async def _setup_cmd(self, interaction, kind, channel, message, title, use_embed):
        if interaction.guild is None:
            return
        try:
            message = validate_string_length(
                message, min_len=1, max_len=4000 if use_embed else 2000
            )
            if title:
                title = validate_string_length(title, min_len=1, max_len=256)
        except ValidationError as e:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", e.user_message), ephemeral=True
            )

        await self.bot.db.set_greeting(
            interaction.guild.id,
            kind,
            enabled=1,
            channel_id=channel.id,
            message=message,
            title=title,
            use_embed=int(use_embed),
            color=AUTOMATION_CONFIG["default_color"],
        )
        await interaction.response.send_message(
            embed=success_embed(
                "Đã cấu hình",
                f"{'Lời chào' if kind == 'welcome' else 'Lời tạm biệt'} sẽ gửi vào "
                f"{channel.mention}.\nDùng placeholder: `{{user_mention}}`, `{{user_name}}`, "
                f"`{{server}}`, `{{member_count}}`.",
            ),
            ephemeral=True,
        )

    @greeting.command(name="welcome", description="Bật & cấu hình lời chào")
    @app_commands.describe(
        channel="Channel gửi lời chào",
        message="Nội dung (hỗ trợ placeholder)",
        title="Tiêu đề embed (tùy chọn)",
        use_embed="Gửi dạng embed?",
    )
    @require_guild_permissions(manage_guild=True)
    async def welcome(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
        title: str | None = None,
        use_embed: bool = True,
    ):
        await self._setup_cmd(
            interaction, "welcome", channel, message, title, use_embed
        )

    @greeting.command(name="goodbye", description="Bật & cấu hình lời tạm biệt")
    @app_commands.describe(
        channel="Channel gửi lời tạm biệt",
        message="Nội dung (hỗ trợ placeholder)",
        title="Tiêu đề embed (tùy chọn)",
        use_embed="Gửi dạng embed?",
    )
    @require_guild_permissions(manage_guild=True)
    async def goodbye(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
        title: str | None = None,
        use_embed: bool = True,
    ):
        await self._setup_cmd(
            interaction, "goodbye", channel, message, title, use_embed
        )

    @greeting.command(name="disable", description="Tắt lời chào hoặc tạm biệt")
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="Lời chào", value="welcome"),
            app_commands.Choice(name="Lời tạm biệt", value="goodbye"),
        ]
    )
    @require_guild_permissions(manage_guild=True)
    async def disable(
        self, interaction: discord.Interaction, kind: app_commands.Choice[str]
    ):
        if interaction.guild is None:
            return
        await self.bot.db.set_greeting(interaction.guild.id, kind.value, enabled=0)
        await interaction.response.send_message(
            embed=success_embed("Đã tắt", f"Đã tắt {kind.name.lower()}."),
            ephemeral=True,
        )

    @greeting.command(
        name="test", description="Gửi thử lời chào/tạm biệt cho chính bạn"
    )
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="Lời chào", value="welcome"),
            app_commands.Choice(name="Lời tạm biệt", value="goodbye"),
        ]
    )
    @require_guild_permissions(manage_guild=True)
    async def test(
        self, interaction: discord.Interaction, kind: app_commands.Choice[str]
    ):
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            return
        await self._send_greeting(interaction.user, kind.value)
        await interaction.response.send_message(
            embed=success_embed("Đã gửi thử", "Kiểm tra channel đã cấu hình nhé."),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Greetings(bot))
