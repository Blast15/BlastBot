"""Cấu hình hệ thống ticket."""

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.base import require_guild_permissions
from utils.constants import COLORS, TICKET_CONFIG
from utils.embeds import create_embed, error_embed, success_embed


class TicketSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ticket = app_commands.Group(
        name="ticket",
        description="Cấu hình hệ thống ticket",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    @ticket.command(name="transcripts", description="Đặt channel lưu transcript")
    @require_guild_permissions(manage_guild=True)
    async def transcripts(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        if interaction.guild is None:
            return
        await self.bot.db.update_ticket_settings(
            interaction.guild.id, transcript_channel_id=channel.id
        )
        await interaction.response.send_message(
            embed=success_embed("Đã đặt", f"Transcript sẽ lưu vào {channel.mention}."),
            ephemeral=True,
        )

    @ticket.command(name="limit", description="Số ticket tối đa mỗi user")
    @require_guild_permissions(manage_guild=True)
    async def limit(self, interaction: discord.Interaction, amount: int):
        if interaction.guild is None:
            return
        amount = max(1, min(TICKET_CONFIG["max_limit"], amount))
        await self.bot.db.update_ticket_settings(
            interaction.guild.id, ticket_limit=amount
        )
        await interaction.response.send_message(
            embed=success_embed("Đã đặt", f"Giới hạn: **{amount}** ticket/user."),
            ephemeral=True,
        )

    @ticket.command(
        name="autoclose",
        description="Tự đóng ticket sau N giờ không hoạt động (0 = tắt)",
    )
    @require_guild_permissions(manage_guild=True)
    async def autoclose(self, interaction: discord.Interaction, hours: int):
        if interaction.guild is None:
            return
        hours = max(0, min(720, hours))
        await self.bot.db.update_ticket_settings(
            interaction.guild.id, autoclose_hours=hours
        )
        msg = (
            "Đã tắt autoclose."
            if hours == 0
            else f"Ticket sẽ tự đóng sau **{hours} giờ** không hoạt động."
        )
        await interaction.response.send_message(
            embed=success_embed("Autoclose", msg), ephemeral=True
        )

    @ticket.command(name="claimmode", description="Chế độ claim")
    @app_commands.choices(
        mode=[
            app_commands.Choice(
                name="Tất cả staff thấy, chỉ claimer trả lời", value="reply_only"
            ),
            app_commands.Choice(name="Tất cả staff thấy & trả lời", value="view_all"),
        ]
    )
    @require_guild_permissions(manage_guild=True)
    async def claimmode(
        self, interaction: discord.Interaction, mode: app_commands.Choice[str]
    ):
        if interaction.guild is None:
            return
        await self.bot.db.update_ticket_settings(
            interaction.guild.id, claim_mode=mode.value
        )
        await interaction.response.send_message(
            embed=success_embed("Claim mode", f"Đã đặt: {mode.name}"), ephemeral=True
        )

    # ---- staff ----
    @ticket.command(name="addsupport", description="Thêm user/role làm support")
    @require_guild_permissions(manage_guild=True)
    async def addsupport(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
    ):
        if interaction.guild is None:
            return
        entity = user or role
        if not entity:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Chọn user hoặc role."), ephemeral=True
            )
        await self.bot.db.add_staff(
            interaction.guild.id, entity.id, role is not None, "support"
        )
        await interaction.response.send_message(
            embed=success_embed("Đã thêm", f"{entity.mention} là support."),
            ephemeral=True,
        )

    @ticket.command(name="removesupport", description="Gỡ support")
    @require_guild_permissions(manage_guild=True)
    async def removesupport(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
    ):
        if interaction.guild is None:
            return
        entity = user or role
        if not entity:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Chọn user hoặc role."), ephemeral=True
            )
        await self.bot.db.remove_staff(interaction.guild.id, entity.id, "support")
        await interaction.response.send_message(
            embed=success_embed("Đã gỡ", f"{entity.mention} không còn là support."),
            ephemeral=True,
        )

    @ticket.command(name="viewstaff", description="Xem danh sách staff")
    @require_guild_permissions(manage_guild=True)
    async def viewstaff(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return
        staff = await self.bot.db.get_staff(interaction.guild.id)
        if not staff:
            return await interaction.response.send_message(
                embed=create_embed(
                    title="Staff",
                    description="Chưa có staff nào.",
                    color=COLORS["info"],
                ),
                ephemeral=True,
            )
        lines = []
        for e in staff:
            mention = (
                f"<@&{e['entity_id']}>" if e["is_role"] else f"<@{e['entity_id']}>"
            )
            lines.append(f"{mention} — `{e['type']}`")
        await interaction.response.send_message(
            embed=create_embed(
                title="🛡️ Ticket Staff",
                description="\n".join(lines),
                color=COLORS["info"],
            ),
            ephemeral=True,
        )

    # ---- blacklist ----
    @ticket.command(name="blacklist", description="Chặn/bỏ chặn user/role khỏi ticket")
    @require_guild_permissions(manage_guild=True)
    async def blacklist(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
    ):
        if interaction.guild is None:
            return
        entity = user or role
        if not entity:
            return await interaction.response.send_message(
                embed=error_embed("Lỗi", "Chọn user hoặc role."), ephemeral=True
            )
        current = await self.bot.db.get_blacklist(interaction.guild.id)
        already = any(b["entity_id"] == entity.id for b in current)
        await self.bot.db.set_blacklist(
            interaction.guild.id, entity.id, role is not None, not already
        )
        txt = "đã được bỏ chặn" if already else "đã bị chặn"
        await interaction.response.send_message(
            embed=success_embed("Blacklist", f"{entity.mention} {txt}."), ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(TicketSetup(bot))
