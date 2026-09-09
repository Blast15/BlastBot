from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from blastbot.core.bot import BlastBot
from blastbot.shared.embeds import info, success, warning
from blastbot.shared.permissions import require_guild_permissions

AUTOMOD_RULE_PREFIX = "BlastBot · "
AUTOMOD_RULE_NAMES = (
    f"{AUTOMOD_RULE_PREFIX}Anti-spam",
    f"{AUTOMOD_RULE_PREFIX}Mention spam",
    f"{AUTOMOD_RULE_PREFIX}Invite links",
)
AUTOMOD_INVITE_KEYWORDS = ("*discord.gg/*", "*discord.com/invite/*")


class ConfigurationCog(commands.Cog):
    config = app_commands.Group(
        name="config",
        description="Cấu hình chung của BlastBot",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )
    automod = app_commands.Group(
        name="automod",
        description="AutoMod kiểu Dyno dùng rule native của Discord",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot

    @staticmethod
    def _automod_actions(alert_channel_id: int | None) -> list[discord.AutoModRuleAction]:
        actions = [
            discord.AutoModRuleAction(
                custom_message="Tin nhắn đã bị AutoMod của BlastBot chặn."
            )
        ]
        if alert_channel_id is not None:
            actions.append(discord.AutoModRuleAction(channel_id=alert_channel_id))
        return actions

    @staticmethod
    def _automod_specs(
        mention_limit: int,
    ) -> tuple[tuple[str, discord.AutoModTrigger], ...]:
        return (
            (
                AUTOMOD_RULE_NAMES[0],
                discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.spam),
            ),
            (
                AUTOMOD_RULE_NAMES[1],
                discord.AutoModTrigger(
                    mention_limit=mention_limit,
                    mention_raid_protection=True,
                ),
            ),
            (
                AUTOMOD_RULE_NAMES[2],
                discord.AutoModTrigger(keyword_filter=list(AUTOMOD_INVITE_KEYWORDS)),
            ),
        )

    @config.command(
        name="logchannel", description="Đặt hoặc tắt channel nhận moderation/report log"
    )
    @require_guild_permissions(manage_guild=True)
    async def log_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.guild_config.set_log_channel(
            interaction.guild_id, channel.id if channel else None
        )
        text = f"Log channel: {channel.mention}." if channel else "Đã tắt log channel."
        await interaction.response.send_message(embed=success("Đã cập nhật", text), ephemeral=True)

    @config.command(name="view", description="Xem cấu hình chung")
    @require_guild_permissions(manage_guild=True)
    async def view(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        data = await self.bot.app.guild_config.get(interaction.guild_id)
        log_channel = f"<#{data.log_channel_id}>" if data.log_channel_id else "Chưa cấu hình"
        await interaction.response.send_message(
            embed=info("Cấu hình BlastBot", f"**Kênh moderation/report:** {log_channel}"),
            ephemeral=True,
        )

    @automod.command(
        name="setup",
        description="Bật anti-spam, chống mention spam và chặn link invite",
    )
    @require_guild_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_guild=True)
    async def automod_setup(
        self,
        interaction: discord.Interaction,
        mention_limit: app_commands.Range[int, 2, 50] = 5,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        config = await self.bot.app.guild_config.get(guild.id)
        configured_channel = (
            guild.get_channel(config.log_channel_id) if config.log_channel_id else None
        )
        alert_channel_id = (
            configured_channel.id
            if isinstance(configured_channel, discord.TextChannel)
            else None
        )
        actions = self._automod_actions(alert_channel_id)
        existing = {rule.name: rule for rule in await guild.fetch_automod_rules()}
        created = 0
        updated = 0
        failures: list[str] = []

        for name, trigger in self._automod_specs(int(mention_limit)):
            rule = existing.get(name)
            try:
                if rule is None:
                    await guild.create_automod_rule(
                        name=name,
                        event_type=discord.AutoModRuleEventType.message_send,
                        trigger=trigger,
                        actions=actions,
                        enabled=True,
                        reason=f"BlastBot AutoMod setup by {interaction.user}",
                    )
                    created += 1
                    continue

                if rule.trigger.type is not trigger.type:
                    failures.append(f"{name}: trigger type đã bị thay đổi thủ công")
                    continue

                await rule.edit(
                    trigger=trigger,
                    actions=actions,
                    enabled=True,
                    reason=f"BlastBot AutoMod update by {interaction.user}",
                )
                updated += 1
            except discord.HTTPException as exc:
                failures.append(f"{name}: Discord API trả về HTTP {exc.status}")

        alert_text = (
            f"<#{alert_channel_id}>"
            if alert_channel_id is not None
            else "không có (hãy dùng `/config logchannel` nếu cần alert)"
        )
        detail = (
            f"Tạo mới: **{created}** · Cập nhật: **{updated}**\n"
            f"Mention limit: **{mention_limit}** · Alert: {alert_text}"
        )
        if failures:
            detail += "\n\nKhông áp dụng được:\n- " + "\n- ".join(failures)
            embed = warning("AutoMod đã cập nhật một phần", detail)
        else:
            embed = success("AutoMod đã bật", detail)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @automod.command(name="status", description="Xem trạng thái các rule AutoMod của BlastBot")
    @require_guild_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_guild=True)
    async def automod_status(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            return

        rules = {rule.name: rule for rule in await guild.fetch_automod_rules()}
        lines = []
        for name in AUTOMOD_RULE_NAMES:
            rule = rules.get(name)
            if rule is None:
                state = "chưa tạo"
            elif rule.enabled:
                state = "đang bật"
            else:
                state = "đang tắt"
            lines.append(f"**{name.removeprefix(AUTOMOD_RULE_PREFIX)}:** {state}")

        await interaction.response.send_message(
            embed=info("BlastBot AutoMod", "\n".join(lines)),
            ephemeral=True,
        )

    @automod.command(
        name="disable", description="Tắt các rule AutoMod do BlastBot quản lý"
    )
    @require_guild_permissions(manage_guild=True)
    @app_commands.checks.bot_has_permissions(manage_guild=True)
    async def automod_disable(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            return

        await interaction.response.defer(ephemeral=True)
        rules = await guild.fetch_automod_rules()
        disabled = 0
        failures: list[str] = []
        for rule in rules:
            if rule.name not in AUTOMOD_RULE_NAMES or not rule.enabled:
                continue
            try:
                await rule.edit(
                    enabled=False,
                    reason=f"BlastBot AutoMod disabled by {interaction.user}",
                )
                disabled += 1
            except discord.HTTPException as exc:
                failures.append(f"{rule.name}: HTTP {exc.status}")

        if failures:
            detail = f"Đã tắt **{disabled}** rule.\n- " + "\n- ".join(failures)
            embed = warning("AutoMod đã tắt một phần", detail)
        else:
            embed = success("AutoMod đã tắt", f"Đã tắt **{disabled}** rule do BlastBot quản lý.")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(ConfigurationCog(bot))
