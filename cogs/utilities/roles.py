"""Role management commands"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
from utils.embeds import success_embed, error_embed, info_embed, create_embed
from utils.views import RoleSelectMenu, PersistentView
from utils.constants import COLORS, EMOJIS


class RoleMenuView(PersistentView):
    """Persistent view cho role menu"""
    
    def __init__(self, roles: List[discord.Role], mode: str = "toggle"):
        super().__init__()
        self.roles = roles
        self.mode = mode
        
        max_values = len(roles) if mode == "toggle" else 1
        self.add_item(
            RoleSelectMenu(
                roles=roles,
                placeholder="Chọn roles bạn muốn...",
                min_values=0,
                max_values=max_values
            )
        )


class RolesCommand(commands.Cog):
    """Role management cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('BlastBot.Utilities.Roles')
    
    @app_commands.command(
        name="rolemenu",
        description="🎭 Tạo menu interactive để members tự chọn roles"
    )
    @app_commands.describe(
        roles="Các roles (cách nhau bằng dấu phẩy hoặc mention)",
        title="Tiêu đề của menu",
        description="Mô tả menu (optional)",
        mode="Chế độ: toggle (nhiều role) hoặc single (1 role)"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Toggle - Chọn nhiều roles", value="toggle"),
        app_commands.Choice(name="Single - Chỉ 1 role", value="single"),
    ])
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    async def rolemenu(
        self,
        interaction: discord.Interaction,
        roles: str,
        title: str = "Chọn Roles",
        description: Optional[str] = None,
        mode: str = "toggle"
    ):
        """Tạo role selection menu"""
        try:
            await interaction.response.defer()
            
            if not interaction.guild:
                await interaction.followup.send(
                    embed=error_embed("Lệnh này chỉ dùng trong server!"),
                    ephemeral=True
                )
                return
            
            # Parse roles
            role_list = []
            role_mentions = roles.replace(',', ' ').split()
            
            for mention in role_mentions:
                role_id = None
                if mention.startswith('<@&') and mention.endswith('>'):
                    try:
                        role_id = int(mention[3:-1])
                    except ValueError:
                        pass
                
                if role_id:
                    role = interaction.guild.get_role(role_id)
                    if role:
                        role_list.append(role)
                else:
                    role = discord.utils.get(interaction.guild.roles, name=mention.strip())
                    if role:
                        role_list.append(role)
            
            if not role_list:
                await interaction.followup.send(
                    embed=error_embed(
                        "Không tìm thấy role nào!",
                        "Mention role hoặc ghi tên chính xác, cách nhau bằng dấu phẩy."
                    ),
                    ephemeral=True
                )
                return
            
            if len(role_list) > 25:
                await interaction.followup.send(
                    embed=error_embed("Tối đa 25 roles cho một menu!"),
                    ephemeral=True
                )
                return
            
            if not isinstance(interaction.user, discord.Member):
                await interaction.followup.send(
                    embed=error_embed("Không thể xác định member!"),
                    ephemeral=True
                )
                return
            
            bot_member = interaction.guild.get_member(self.bot.user.id)
            if not bot_member:
                await interaction.followup.send(
                    embed=error_embed("Không thể xác định bot member!"),
                    ephemeral=True
                )
                return
            
            for role in role_list:
                if role >= bot_member.top_role:
                    await interaction.followup.send(
                        embed=error_embed(
                            f"Không thể quản lý role {role.mention}!",
                            "Role này cao hơn hoặc bằng highest role của bot."
                        ),
                        ephemeral=True
                    )
                    return
            
            desc = description or "Chọn các roles bạn muốn từ menu bên dưới."
            desc += f"\n\n**Chế độ:** {mode.title()}"
            desc += "\n**Roles:**\n" + "\n".join([f"• {r.mention}" for r in role_list])
            
            embed = create_embed(
                title=f"{EMOJIS.get('role', '🎭')} {title}",
                description=desc,
                color=COLORS['primary']
            )
            
            view = RoleMenuView(roles=role_list, mode=mode)
            
            await interaction.followup.send(embed=embed, view=view)
            
            self.logger.info(
                f"Role menu created by {interaction.user} in {interaction.guild.name}"
            )
            
        except Exception as e:
            self.logger.error(f"Error in rolemenu command: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    embed=error_embed(f"Lỗi: {str(e)}"),
                    ephemeral=True
                )
            except discord.HTTPException:
                pass
    
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
                embed=error_embed(f"Lỗi: {str(e)}"),
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
                embed=error_embed(f"Lỗi: {str(e)}"),
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
                embed=error_embed(f"Lỗi: {str(e)}"),
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(RolesCommand(bot))
