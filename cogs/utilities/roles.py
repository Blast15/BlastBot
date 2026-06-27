"""Role management commands"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from utils.embeds import success_embed, error_embed, info_embed, create_embed
from utils.constants import COLORS, EMOJIS, COMMAND_COOLDOWNS


class RolesCommand(commands.Cog):
    """Role management cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('BlastBot.Utilities.Roles')
    
    @app_commands.command(
        name="roleinfo",
        description="ℹ️ Xem thông tin chi tiết về một role"
    )
    @app_commands.describe(role="Role cần xem thông tin")
    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        """Hiển thị thông tin về role"""
        try:
            member_count = len(role.members)
            
            perms = role.permissions
            key_perms = []
            if perms.administrator:
                key_perms.append("👑 Administrator")
            if perms.manage_guild:
                key_perms.append("⚙️ Manage Server")
            if perms.manage_roles:
                key_perms.append("🎭 Manage Roles")
            if perms.manage_channels:
                key_perms.append("📝 Manage Channels")
            if perms.kick_members:
                key_perms.append("👢 Kick Members")
            if perms.ban_members:
                key_perms.append("🔨 Ban Members")
            if perms.moderate_members:
                key_perms.append("⏱️ Timeout Members")
            
            embed = create_embed(
                title=f"🎭 Role: {role.name}",
                description=f"**ID:** `{role.id}`",
                color=role.color.value if role.color.value != 0 else COLORS['primary']
            )
            
            embed.add_field(
                name="📊 Thông tin",
                value=(
                    f"**Members:** {member_count}\n"
                    f"**Position:** {role.position}\n"
                    f"**Mentionable:** {'✅' if role.mentionable else '❌'}\n"
                    f"**Hoisted:** {'✅' if role.hoist else '❌'}\n"
                    f"**Managed:** {'✅' if role.managed else '❌'}"
                ),
                inline=True
            )
            
            embed.add_field(
                name="🎨 Màu sắc",
                value=(
                    f"**Hex:** `{str(role.color)}`\n"
                    f"**RGB:** `{role.color.to_rgb()}`"
                ),
                inline=True
            )
            
            if key_perms:
                embed.add_field(
                    name="🔑 Key Permissions",
                    value="\n".join(key_perms[:10]),
                    inline=False
                )
            
            if role.icon:
                embed.set_thumbnail(url=role.icon.url)
            
            embed.set_footer(
                text=f"Created: {role.created_at.strftime('%d/%m/%Y %H:%M')}"
            )
            
            await interaction.response.send_message(embed=embed)
            
            self.logger.info(f"{interaction.user} viewed info for role {role.name}")
            
        except Exception as e:
            self.logger.error(f"Error in roleinfo command: {e}", exc_info=True)
            await interaction.response.send_message(
                embed=error_embed("Đã xảy ra lỗi. Vui lòng thử lại sau."),
                ephemeral=True
            )
    
    @app_commands.command(
        name="roleadd",
        description="➕ Thêm role cho một member"
    )
    @app_commands.describe(member="Member cần thêm role", role="Role cần thêm")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def roleadd(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role
    ):
        """Thêm role cho member"""
        try:
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    embed=error_embed("Không thể xác định member!"),
                    ephemeral=True
                )
                return
            
            if interaction.guild and role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message(
                    embed=error_embed(
                        "Không thể thêm role này!",
                        "Role cao hơn hoặc bằng highest role của bạn."
                    ),
                    ephemeral=True
                )
                return
            
            if role in member.roles:
                await interaction.response.send_message(
                    embed=error_embed(f"{member.mention} đã có role {role.mention}!"),
                    ephemeral=True
                )
                return
            
            await member.add_roles(role, reason=f"Role added by {interaction.user}")
            
            await interaction.response.send_message(
                embed=success_embed(f"✅ Đã thêm role {role.mention} cho {member.mention}")
            )
            
            self.logger.info(f"{interaction.user} added role {role.name} to {member}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Bot không có quyền quản lý role này!"),
                ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Error in roleadd command: {e}", exc_info=True)
            await interaction.response.send_message(
                embed=error_embed("Đã xảy ra lỗi. Vui lòng thử lại sau."),
                ephemeral=True
            )
    
    @app_commands.command(
        name="roleremove",
        description="➖ Xóa role khỏi một member"
    )
    @app_commands.describe(member="Member cần xóa role", role="Role cần xóa")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
    async def roleremove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role
    ):
        """Xóa role khỏi member"""
        try:
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message(
                    embed=error_embed("Không thể xác định member!"),
                    ephemeral=True
                )
                return
            
            if interaction.guild and role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message(
                    embed=error_embed(
                        "Không thể xóa role này!",
                        "Role cao hơn hoặc bằng highest role của bạn."
                    ),
                    ephemeral=True
                )
                return
            
            if role not in member.roles:
                await interaction.response.send_message(
                    embed=error_embed(f"{member.mention} không có role {role.mention}!"),
                    ephemeral=True
                )
                return
            
            await member.remove_roles(role, reason=f"Role removed by {interaction.user}")
            
            await interaction.response.send_message(
                embed=success_embed(f"✅ Đã xóa role {role.mention} khỏi {member.mention}")
            )
            
            self.logger.info(f"{interaction.user} removed role {role.name} from {member}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Bot không có quyền quản lý role này!"),
                ephemeral=True
            )
        except Exception as e:
            self.logger.error(f"Error in roleremove command: {e}", exc_info=True)
            await interaction.response.send_message(
                embed=error_embed("Đã xảy ra lỗi. Vui lòng thử lại sau."),
                ephemeral=True
            )
