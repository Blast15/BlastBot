from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from weakref import WeakValueDictionary

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy.exc import SQLAlchemyError

from blastbot.core.bot import BlastBot
from blastbot.database.models import TempRole
from blastbot.modules.moderation.service import ModerationRecord
from blastbot.modules.moderation.ui import ConfirmView
from blastbot.shared.embeds import error, info, success, warning
from blastbot.shared.permissions import (
    require_guild_permissions,
    validate_member_manage,
    validate_moderation_target,
    validate_role_manage,
)
from blastbot.shared.responder import send_interaction
from blastbot.shared.time import ensure_utc
from blastbot.shared.validation import require_text

logger = logging.getLogger(__name__)

COMMON_REASONS = (
    "Spam",
    "Quấy rối",
    "Nội dung không phù hợp",
    "Vi phạm nội quy",
    "Lừa đảo/phishing",
)


async def _reason_autocomplete(
    _: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    text = current.casefold()
    return [
        app_commands.Choice(name=reason, value=reason)
        for reason in COMMON_REASONS
        if text in reason.casefold()
    ][:25]


class ModerationCog(commands.Cog):
    SOFTBAN_UNBAN_ATTEMPTS = 3

    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot
        self._temp_role_locks: WeakValueDictionary[tuple[int, int, int], asyncio.Lock] = (
            WeakValueDictionary()
        )
        self.temp_role_cleanup.add_exception_type(SQLAlchemyError)
        self.temp_role_cleanup.start()

    async def cog_unload(self) -> None:
        self.temp_role_cleanup.cancel()
        task = self.temp_role_cleanup.get_task()
        if task is not None:
            with suppress(asyncio.CancelledError):
                await task

    def _record(
        self,
        interaction: discord.Interaction,
        target: discord.abc.User,
        reason: str | None,
    ) -> ModerationRecord:
        if interaction.guild_id is None:
            raise app_commands.NoPrivateMessage()
        return ModerationRecord(
            guild_id=interaction.guild_id,
            moderator_id=interaction.user.id,
            target_id=target.id,
            target_str=str(target),
            reason=require_text(reason, maximum=1000) if reason else None,
        )

    async def _validate_target(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> bool:
        guild = interaction.guild
        actor = interaction.user
        if guild is None or not isinstance(actor, discord.Member):
            await send_interaction(
                interaction, content="Lệnh này chỉ dùng trong server.", ephemeral=True
            )
            return False
        problem = validate_moderation_target(guild, actor, member)
        if problem:
            await send_interaction(
                interaction, embed=error("Không thể thực hiện", problem), ephemeral=True
            )
            return False
        return True

    async def _confirm(
        self, interaction: discord.Interaction, title: str, description: str
    ) -> bool:
        view = ConfirmView(interaction.user.id)
        await interaction.response.send_message(
            embed=warning(title, description), view=view, ephemeral=True
        )
        await view.wait()
        if view.value is not True:
            await interaction.edit_original_response(
                embed=info("Đã hủy", "Không có thay đổi nào được thực hiện."), view=None
            )
            return False
        return True

    async def _emit_log(
        self,
        interaction: discord.Interaction,
        *,
        action: str,
        target: discord.abc.User,
        reason: str | None,
        extra: str | None = None,
    ) -> None:
        if interaction.guild is None:
            return
        channel_id = await self.bot.app.moderation_repo.get_log_channel_id(interaction.guild.id)
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            embed = info(
                f"Moderation · {action}",
                f"**Target:** {target.mention} (`{target.id}`)\n"
                f"**Moderator:** {interaction.user.mention}\n"
                f"**Reason:** {reason or 'Không có'}"
                + (f"\n**Chi tiết:** {extra}" if extra else ""),
            )
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                logger.warning("Failed to send moderation log", exc_info=True)

    async def _persist_action(
        self, action: str, record: ModerationRecord, **extra: object
    ) -> bool:
        try:
            await self.bot.app.moderation.record_action(action, record, **extra)
        except SQLAlchemyError:
            logger.exception(
                "Discord moderation action succeeded but audit persistence failed",
                extra={
                    "guild_id": record.guild_id,
                    "user_id": record.target_id,
                    "operation": action,
                    "moderator_id": record.moderator_id,
                },
            )
            return False
        return True

    async def _unban_after_softban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> bool:
        guild = interaction.guild
        if guild is None:
            return False
        for attempt in range(self.SOFTBAN_UNBAN_ATTEMPTS):
            try:
                await guild.unban(member, reason=f"Softban by {interaction.user}")
                return True
            except discord.NotFound:
                logger.warning(
                    "Softban unban returned not found; target is already not banned",
                    extra={
                        "guild_id": guild.id,
                        "user_id": member.id,
                        "moderator_id": interaction.user.id,
                        "operation": "SOFTBAN_UNBAN",
                    },
                )
                return True
            except discord.Forbidden:
                logger.exception(
                    "Softban ban succeeded but unban is forbidden",
                    extra={
                        "guild_id": guild.id,
                        "user_id": member.id,
                        "moderator_id": interaction.user.id,
                        "operation": "SOFTBAN_UNBAN",
                    },
                )
                return False
            except discord.HTTPException as exc:
                transient = exc.status == 429 or exc.status >= 500
                if not transient or attempt + 1 == self.SOFTBAN_UNBAN_ATTEMPTS:
                    logger.exception(
                        "Softban ban succeeded but unban failed%s",
                        " after all retries" if transient else " with a non-retryable error",
                        extra={
                            "guild_id": guild.id,
                            "user_id": member.id,
                            "moderator_id": interaction.user.id,
                            "operation": "SOFTBAN_UNBAN",
                        },
                    )
                    return False
                await asyncio.sleep(0.5 * (attempt + 1))
        return False  # pragma: no cover

    async def _grant_temp_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        duration_minutes: int,
        reason: str | None,
    ) -> datetime:
        guild = interaction.guild
        if guild is None:
            raise app_commands.NoPrivateMessage()
        lock = self._temp_role_lock(guild.id, member.id, role.id)
        async with lock:
            previous = await self.bot.app.moderation_repo.get_temp_role(
                guild.id, member.id, role.id
            )
            expires = await self.bot.app.moderation.add_temp_role(
                guild_id=guild.id,
                user_id=member.id,
                role_id=role.id,
                duration_minutes=duration_minutes,
            )
            try:
                await member.add_roles(
                    role, reason=f"Temporary role by {interaction.user}: {reason or 'N/A'}"
                )
            except (discord.Forbidden, discord.HTTPException):
                try:
                    if previous is None:
                        await self.bot.app.moderation_repo.remove_temp_role(
                            guild.id, member.id, role.id
                        )
                    else:
                        await self.bot.app.moderation_repo.put_temp_role(
                            guild_id=guild.id,
                            user_id=member.id,
                            role_id=role.id,
                            expires_at=previous.expires_at,
                        )
                except SQLAlchemyError:
                    logger.exception(
                        "Failed to restore temp-role intent after Discord add failure",
                        extra={
                            "guild_id": guild.id,
                            "user_id": member.id,
                            "role_id": role.id,
                            "operation": "TEMPROLE_COMPENSATE",
                        },
                    )
                raise
            return expires

    def _temp_role_lock(self, guild_id: int, user_id: int, role_id: int) -> asyncio.Lock:
        locks = getattr(self, "_temp_role_locks", None)
        if locks is None:
            locks = self._temp_role_locks = WeakValueDictionary()
        key = (guild_id, user_id, role_id)
        lock = locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            # Weak values keep per-target serialization without retaining inactive keys.
            locks[key] = lock
        return lock

    @app_commands.command(name="kick", description="Kick một thành viên khỏi server")
    @app_commands.guild_only()
    @app_commands.default_permissions(kick_members=True)
    @require_guild_permissions(kick_members=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    @app_commands.autocomplete(reason=_reason_autocomplete)
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
    ) -> None:
        if not await self._validate_target(interaction, member):
            return
        if not await self._confirm(
            interaction, "Xác nhận kick", f"Kick {member.mention} khỏi server?"
        ):
            return
        record = self._record(interaction, member, reason)
        await member.kick(reason=f"{reason or 'Không có lý do'} | by {interaction.user}")
        audit_ok = await self._persist_action("KICK", record)
        await interaction.edit_original_response(
            embed=(
                success("Đã kick", f"Đã kick {member.mention}.")
                if audit_ok
                else warning(
                    "Đã kick, nhưng audit lỗi",
                    f"{member.mention} đã bị kick; bản ghi database chưa được lưu.",
                )
            ),
            view=None,
        )
        await self._emit_log(interaction, action="KICK", target=member, reason=reason)

    @app_commands.command(name="ban", description="Ban một thành viên khỏi server")
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    @require_guild_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    @app_commands.autocomplete(reason=_reason_autocomplete)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
        delete_messages: app_commands.Range[int, 0, 7] = 0,
    ) -> None:
        if not await self._validate_target(interaction, member):
            return
        if not await self._confirm(
            interaction, "Xác nhận ban", f"Ban {member.mention} khỏi server?"
        ):
            return
        record = self._record(interaction, member, reason)
        await member.ban(
            reason=f"{reason or 'Không có lý do'} | by {interaction.user}",
            delete_message_seconds=int(delete_messages) * 86400,
        )
        audit_ok = await self._persist_action(
            "BAN",
            record,
            delete_messages_days=int(delete_messages),
        )
        await interaction.edit_original_response(
            embed=(
                success("Đã ban", f"Đã ban {member.mention}.")
                if audit_ok
                else warning(
                    "Đã ban, nhưng audit lỗi",
                    f"{member.mention} đã bị ban; bản ghi database chưa được lưu.",
                )
            ),
            view=None,
        )
        await self._emit_log(
            interaction,
            action="BAN",
            target=member,
            reason=reason,
            extra=f"Xóa {delete_messages} ngày tin nhắn",
        )

    @app_commands.command(name="softban", description="Ban rồi unban để dọn tin nhắn")
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    @require_guild_permissions(ban_members=True)
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: i.user.id)
    @app_commands.autocomplete(reason=_reason_autocomplete)
    async def softban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
        delete_messages: app_commands.Range[int, 1, 7] = 1,
    ) -> None:
        if not await self._validate_target(interaction, member) or interaction.guild is None:
            return
        if not await self._confirm(interaction, "Xác nhận softban", f"Softban {member.mention}?"):
            return
        record = self._record(interaction, member, reason)
        await interaction.guild.ban(
            member,
            reason=f"{reason or 'Không có lý do'} | by {interaction.user}",
            delete_message_seconds=int(delete_messages) * 86400,
        )
        if not await self._unban_after_softban(interaction, member):
            audit_ok = await self._persist_action(
                "SOFTBAN_PARTIAL",
                record,
                delete_messages_days=int(delete_messages),
                still_banned=True,
            )
            detail = f"{member.mention} vẫn đang bị ban vì bước unban thất bại."
            if not audit_ok:
                detail += " Bản ghi audit database cũng chưa được lưu."
            await interaction.edit_original_response(
                embed=error("Softban chưa hoàn tất", detail), view=None
            )
            await self._emit_log(
                interaction,
                action="SOFTBAN_PARTIAL",
                target=member,
                reason=reason,
                extra="Ban thành công nhưng unban thất bại; user vẫn bị ban",
            )
            return
        audit_ok = await self._persist_action(
            "SOFTBAN", record, delete_messages_days=int(delete_messages)
        )
        await interaction.edit_original_response(
            embed=(
                success("Đã softban", f"Đã softban {member.mention}.")
                if audit_ok
                else warning(
                    "Đã softban, nhưng audit lỗi",
                    f"Softban {member.mention} đã hoàn tất; bản ghi database chưa được lưu.",
                )
            ),
            view=None,
        )
        await self._emit_log(interaction, action="SOFTBAN", target=member, reason=reason)

    @app_commands.command(name="timeout", description="Timeout một thành viên")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @require_guild_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    @app_commands.autocomplete(reason=_reason_autocomplete)
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: app_commands.Range[int, 1, 10080],
        reason: str | None = None,
    ) -> None:
        if not await self._validate_target(interaction, member):
            return
        if not await self._confirm(
            interaction,
            "Xác nhận timeout",
            f"Timeout {member.mention} trong **{duration} phút**?",
        ):
            return
        record = self._record(interaction, member, reason)
        await member.timeout(
            timedelta(minutes=int(duration)),
            reason=f"{reason or 'Không có lý do'} | by {interaction.user}",
        )
        audit_ok = await self._persist_action(
            "TIMEOUT",
            record,
            duration_minutes=int(duration),
        )
        await interaction.edit_original_response(
            embed=(
                success("Đã timeout", f"Đã timeout {member.mention} trong {duration} phút.")
                if audit_ok
                else warning(
                    "Đã timeout, nhưng audit lỗi",
                    f"Timeout đã áp dụng cho {member.mention}; bản ghi database chưa được lưu.",
                )
            ),
            view=None,
        )
        await self._emit_log(interaction, action="TIMEOUT", target=member, reason=reason)

    @app_commands.command(name="slowmode", description="Đặt thời gian chờ giữa tin nhắn trong kênh")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: (i.guild_id, i.channel_id))
    @app_commands.checks.bot_has_permissions(manage_channels=True)
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(seconds="0 để tắt; tối đa 21600 giây (6 giờ)")
    async def slowmode(self, interaction: discord.Interaction,
                       seconds: app_commands.Range[int, 0, 21600]):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error("Không hỗ trợ", "Dùng lệnh trong kênh văn bản cần chỉnh."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        await channel.edit(slowmode_delay=seconds, reason=f"Slowmode by {interaction.user.id}")
        record = ModerationRecord(interaction.guild_id, interaction.user.id, channel.id,
                                  f"#{channel.name}", "Điều chỉnh slowmode")
        audit_ok = await self._persist_action("SLOWMODE", record, seconds=seconds)
        description = f"{channel.mention}: **{seconds} giây**." if seconds else "Đã tắt slowmode."
        await interaction.followup.send(
            embed=success("Đã cập nhật slowmode", description) if audit_ok else warning(
                "Đã cập nhật, nhưng audit lỗi", description + " Bản ghi database chưa được lưu."),
            ephemeral=True,
        )

    @app_commands.command(name="clear", description="Xóa tin nhắn gần đây, bỏ qua tin đã ghim")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    @require_guild_permissions(manage_messages=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def clear(
        self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error("Không hỗ trợ", "Lệnh này cần text channel."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await channel.purge(limit=int(amount), check=lambda m: not m.pinned, bulk=True)
        record = ModerationRecord(
            guild_id=interaction.guild_id or 0,
            moderator_id=interaction.user.id,
            target_id=channel.id,
            target_str=f"#{channel.name}",
            reason=None,
        )
        audit_ok = await self._persist_action("CLEAR", record, deleted=len(deleted))
        await interaction.followup.send(
            embed=(
                success("Đã xóa", f"Đã xóa **{len(deleted)}** tin nhắn (bỏ qua pinned).")
                if audit_ok
                else warning(
                    "Đã xóa, nhưng audit lỗi",
                    f"Đã xóa **{len(deleted)}** tin nhắn; bản ghi database chưa được lưu.",
                )
            ),
            ephemeral=True,
        )

    @app_commands.command(name="temprole", description="Cấp role tạm thời cho member")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @require_guild_permissions(manage_roles=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    async def temprole(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        duration: app_commands.Range[int, 1, 40320],
        reason: str | None = None,
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return
        problem = validate_member_manage(interaction.guild, interaction.user, member)
        if problem is None:
            problem = validate_role_manage(interaction.guild, interaction.user, role)
        if problem:
            await interaction.response.send_message(
                embed=error("Không thể cấp role", problem), ephemeral=True
            )
            return
        record = self._record(interaction, member, reason)
        expires = await self._grant_temp_role(
            interaction, member, role, int(duration), reason
        )
        audit_ok = await self._persist_action(
            "TEMPROLE",
            record,
            role_id=role.id,
            expires_at=expires.isoformat(),
        )
        await interaction.response.send_message(
            embed=(
                success(
                    "Đã cấp role tạm",
                    f"{member.mention} nhận {role.mention} đến <t:{int(expires.timestamp())}:F>.",
                )
                if audit_ok
                else warning(
                    "Đã cấp role, nhưng audit lỗi",
                    f"Role tạm đã được cấp và vẫn có lịch cleanup đến "
                    f"<t:{int(expires.timestamp())}:F>; bản ghi moderation chưa được lưu.",
                )
            )
        )

    @app_commands.command(name="warn", description="Cảnh cáo một thành viên")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @require_guild_permissions(moderate_members=True)
    @app_commands.autocomplete(reason=_reason_autocomplete)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None,
    ) -> None:
        if not await self._validate_target(interaction, member):
            return
        count = await self.bot.app.moderation.warn(self._record(interaction, member, reason))
        await interaction.response.send_message(
            embed=success("Đã cảnh cáo", f"{member.mention} hiện có **{count}** cảnh cáo."),
            ephemeral=True,
        )
        await self._emit_log(interaction, action="WARN", target=member, reason=reason)

    @app_commands.command(name="warnings", description="Xem số cảnh cáo của thành viên")
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @require_guild_permissions(moderate_members=True)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        if interaction.guild_id is None:
            return
        count = await self.bot.app.moderation.warnings(interaction.guild_id, member.id)
        await interaction.response.send_message(
            embed=info("Cảnh cáo", f"{member.mention} có **{count}** cảnh cáo."),
            ephemeral=True,
        )

    async def _cleanup_temp_roles(self, now: datetime) -> None:
        for item in await self.bot.app.moderation_repo.expired_temp_roles(now):
            async with self._temp_role_lock(item.guild_id, item.user_id, item.role_id):
                current = await self.bot.app.moderation_repo.get_temp_role(
                    item.guild_id, item.user_id, item.role_id
                )
                if current is None or ensure_utc(current.expires_at) > ensure_utc(now):
                    continue
                await self._cleanup_temp_role(current)

    async def _cleanup_temp_role(self, item: TempRole) -> None:
        guild_id = item.guild_id
        user_id = item.user_id
        role_id = item.role_id
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await self.bot.app.moderation_repo.remove_temp_role(guild_id, user_id, role_id)
            return
        member = guild.get_member(user_id)
        role = guild.get_role(role_id)
        if member is None or role is None:
            await self.bot.app.moderation_repo.remove_temp_role(guild_id, user_id, role_id)
            return
        try:
            await member.remove_roles(role, reason="Temporary role expired")
        except discord.Forbidden:
            logger.warning(
                "Cannot remove expired temp role",
                extra={
                    "guild_id": guild.id,
                    "user_id": member.id,
                    "operation": "temp_role_cleanup",
                },
            )
            return
        except discord.HTTPException:
            logger.exception("Discord API error removing temp role")
            return
        await self.bot.app.moderation_repo.remove_temp_role(guild_id, user_id, role_id)

    @tasks.loop(minutes=1.0)
    async def temp_role_cleanup(self) -> None:
        await self._cleanup_temp_roles(datetime.now(UTC))

    @temp_role_cleanup.error
    async def temp_role_cleanup_error(self, exception: BaseException) -> None:
        logger.exception(
            "Background task temp_role_cleanup failed",
            exc_info=exception,
            extra={
                "operation": "temp_role_cleanup",
                "error_type": type(exception).__name__,
            },
        )

    @temp_role_cleanup.before_loop
    async def before_temp_role_cleanup(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(ModerationCog(bot))
