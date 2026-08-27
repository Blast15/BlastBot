from __future__ import annotations

import logging
from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from blastbot.core.bot import BlastBot
from blastbot.database.models import Greeting
from blastbot.shared.embeds import error, info, success
from blastbot.shared.permissions import require_guild_permissions

logger = logging.getLogger(__name__)

DEFAULT_GREETING_MESSAGES = {
    "welcome": "Chào mừng {user_mention} đến với **{server}**! Thành viên thứ **{member_count}**.",
    "goodbye": "Tạm biệt **{user_name}**. Hẹn gặp lại tại **{server}**!",
}


def render_greeting(template: str, member: discord.Member) -> str:
    return template.format_map(
        {
            "user": str(member),
            "user_mention": member.mention,
            "user_name": member.display_name,
            "server": member.guild.name,
            "member_count": member.guild.member_count or 0,
        }
    )


class AutomationCog(commands.Cog):
    automsg = app_commands.Group(
        name="automsg",
        description="Quản lý auto-message",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )
    greeting = app_commands.Group(
        name="greeting",
        description="Quản lý welcome/goodbye",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot
        self.auto_message_loop.start()

    def cog_unload(self) -> None:
        self.auto_message_loop.cancel()

    @automsg.command(name="add", description="Thêm auto-message định kỳ")
    @require_guild_permissions(manage_guild=True)
    async def automsg_add(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        content: str,
        interval: app_commands.Range[int, 5, 10080],
        use_embed: bool = False,
    ) -> None:
        if interaction.guild_id is None:
            return
        auto_id = await self.bot.app.automation.add_auto_message(
            guild_id=interaction.guild_id,
            channel_id=channel.id,
            content=content,
            interval_minutes=int(interval),
            use_embed=use_embed,
        )
        await interaction.response.send_message(
            embed=success(
                "Đã tạo auto-message",
                f"ID `{auto_id}` · {channel.mention} · mỗi **{interval} phút**.",
            ),
            ephemeral=True,
        )

    @automsg.command(name="list", description="Liệt kê auto-message")
    @require_guild_permissions(manage_guild=True)
    async def automsg_list(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        rows = await self.bot.app.automation_repo.list_auto_messages(
            interaction.guild_id
        )
        if not rows:
            await interaction.response.send_message(
                embed=info("Auto-message", "Chưa có auto-message nào."), ephemeral=True
            )
            return
        lines = [
            f"`{row.id}` · <#{row.channel_id}> · {row.interval_minutes}m · "
            f"{'✅' if row.enabled else '⏸️'} · {'embed' if row.use_embed else 'text'}"
            for row in rows
        ]
        await interaction.response.send_message(
            embed=info("Auto-message", "\n".join(lines)), ephemeral=True
        )

    @automsg.command(name="delete", description="Xóa auto-message")
    @require_guild_permissions(manage_guild=True)
    async def automsg_delete(
        self, interaction: discord.Interaction, auto_id: int
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.automation.remove_auto_message(interaction.guild_id, auto_id)
        await interaction.response.send_message(
            embed=success("Đã xóa", f"Đã xóa auto-message `{auto_id}`."), ephemeral=True
        )

    @automsg.command(name="toggle", description="Bật/tắt auto-message")
    @require_guild_permissions(manage_guild=True)
    async def automsg_toggle(
        self, interaction: discord.Interaction, auto_id: int, enabled: bool
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.automation.set_auto_message_enabled(
            interaction.guild_id, auto_id, enabled
        )
        await interaction.response.send_message(
            embed=success(
                "Đã cập nhật",
                f"Auto-message `{auto_id}`: {'bật' if enabled else 'tắt'}.",
            ),
            ephemeral=True,
        )

    async def _configure_greeting(
        self,
        interaction: discord.Interaction,
        kind: str,
        channel: discord.TextChannel,
        message: str,
        use_embed: bool,
        title: str | None,
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.automation.configure_greeting(
            guild_id=interaction.guild_id,
            kind=kind,
            channel_id=channel.id,
            message=message,
            use_embed=use_embed,
            title=title,
        )
        await interaction.response.send_message(
            embed=success(
                "Đã cấu hình",
                f"{kind.title()} sẽ gửi tại {channel.mention}. Placeholder: "
                "`{user}` `{user_mention}` `{user_name}` `{server}` `{member_count}`",
            ),
            ephemeral=True,
        )

    @greeting.command(name="welcome", description="Cấu hình lời chào thành viên mới")
    @require_guild_permissions(manage_guild=True)
    async def greeting_welcome(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = DEFAULT_GREETING_MESSAGES["welcome"],
        use_embed: bool = True,
        title: str | None = "Chào mừng!",
    ) -> None:
        await self._configure_greeting(
            interaction, "welcome", channel, message, use_embed, title
        )

    @greeting.command(name="goodbye", description="Cấu hình lời tạm biệt")
    @require_guild_permissions(manage_guild=True)
    async def greeting_goodbye(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str = DEFAULT_GREETING_MESSAGES["goodbye"],
        use_embed: bool = True,
        title: str | None = "Tạm biệt!",
    ) -> None:
        await self._configure_greeting(
            interaction, "goodbye", channel, message, use_embed, title
        )

    @greeting.command(name="disable", description="Tắt welcome hoặc goodbye")
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="Welcome", value="welcome"),
            app_commands.Choice(name="Goodbye", value="goodbye"),
        ]
    )
    @require_guild_permissions(manage_guild=True)
    async def greeting_disable(
        self, interaction: discord.Interaction, kind: app_commands.Choice[str]
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.automation.disable_greeting(interaction.guild_id, kind.value)
        await interaction.response.send_message(
            embed=success("Đã tắt", f"Đã tắt {kind.name}."), ephemeral=True
        )

    @greeting.command(name="test", description="Gửi thử welcome/goodbye")
    @app_commands.choices(
        kind=[
            app_commands.Choice(name="Welcome", value="welcome"),
            app_commands.Choice(name="Goodbye", value="goodbye"),
        ]
    )
    @require_guild_permissions(manage_guild=True)
    async def greeting_test(
        self, interaction: discord.Interaction, kind: app_commands.Choice[str]
    ) -> None:
        if interaction.guild_id is None or not isinstance(
            interaction.user, discord.Member
        ):
            return
        row = await self.bot.app.automation_repo.get_greeting(
            interaction.guild_id, kind.value
        )
        if row is None or not row.enabled or row.channel_id is None or not row.message:
            await interaction.response.send_message(
                embed=error("Chưa cấu hình", f"{kind.name} chưa được bật."),
                ephemeral=True,
            )
            return
        channel = (
            interaction.guild.get_channel(row.channel_id) if interaction.guild else None
        )
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error(
                    "Channel không hợp lệ",
                    "Channel đã bị xóa hoặc không còn truy cập được.",
                ),
                ephemeral=True,
            )
            return
        await self._send_greeting(channel, interaction.user, row)
        await interaction.response.send_message(
            embed=success("Đã test", f"Đã gửi thử tại {channel.mention}."),
            ephemeral=True,
        )

    async def _send_greeting(
        self, channel: discord.TextChannel, member: discord.Member, row: Greeting
    ) -> None:
        text = render_greeting(row.message or "", member)
        if row.use_embed:
            card = discord.Embed(
                title=row.title
                or ("Chào mừng!" if row.kind == "welcome" else "Tạm biệt!"),
                description=text,
                color=row.color or discord.Color.blurple(),
            )
            card.set_thumbnail(url=member.display_avatar.url)
            await channel.send(
                embed=card,
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, roles=False, users=True, replied_user=False
                ),
            )
        else:
            await channel.send(
                text,
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, roles=False, users=True, replied_user=False
                ),
            )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        row = await self.bot.app.automation_repo.get_greeting(
            member.guild.id, "welcome"
        )
        if row and row.enabled and row.channel_id and row.message:
            channel = member.guild.get_channel(row.channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    await self._send_greeting(channel, member, row)
                except discord.HTTPException:
                    logger.exception(
                        "Failed to send welcome", extra={"guild_id": member.guild.id}
                    )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return
        row = await self.bot.app.automation_repo.get_greeting(
            member.guild.id, "goodbye"
        )
        if row and row.enabled and row.channel_id and row.message:
            channel = member.guild.get_channel(row.channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    await self._send_greeting(channel, member, row)
                except discord.HTTPException:
                    logger.exception(
                        "Failed to send goodbye", extra={"guild_id": member.guild.id}
                    )

    @tasks.loop(minutes=1.0)
    async def auto_message_loop(self) -> None:
        now = datetime.now(UTC)
        rows = await self.bot.app.automation_repo.due_auto_messages(now)
        for row in rows:
            guild = self.bot.get_guild(row.guild_id)
            channel = guild.get_channel(row.channel_id) if guild else None
            if not isinstance(channel, discord.TextChannel):
                await self.bot.app.automation_repo.toggle_auto_message(
                    row.guild_id, row.id, False
                )
                logger.warning(
                    "Disabled auto-message with missing channel",
                    extra={
                        "guild_id": row.guild_id,
                        "channel_id": row.channel_id,
                        "operation": "automsg",
                    },
                )
                continue
            try:
                if row.use_embed:
                    await channel.send(
                        embed=discord.Embed(
                            description=row.content, color=discord.Color.blurple()
                        ),
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                else:
                    await channel.send(
                        row.content,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
            except discord.HTTPException:
                logger.exception(
                    "Failed to send auto-message", extra={"guild_id": row.guild_id}
                )
                continue
            await self.bot.app.automation_repo.mark_sent(row.id, now)

    @auto_message_loop.error
    async def auto_message_loop_error(self, exception: BaseException) -> None:
        logger.exception(
            "Background task auto_message_loop failed",
            exc_info=exception,
            extra={
                "operation": "auto_message_loop",
                "error_type": type(exception).__name__,
            },
        )

    @auto_message_loop.before_loop
    async def before_auto_message_loop(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(AutomationCog(bot))
