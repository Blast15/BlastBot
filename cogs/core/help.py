"""Help command - Auto-generates command list"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from utils.embeds import create_embed, info_embed
from utils.constants import COLORS, EMOJIS


class HelpCommand(commands.Cog):
    """Dynamic help command that auto-detects all commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('BlastBot.Core.Help')
    
    def _get_command_categories(self) -> dict[str, list[app_commands.Command]]:
        """Tự động phân loại commands theo cog/module."""
        categories = {}
        
        for command in self.bot.tree.walk_commands():
            if isinstance(command, app_commands.Command):
                binding = getattr(command, 'binding', None)
                category = "Other"
                if binding and hasattr(binding, '__module__'):
                    module_parts = binding.__module__.split('.')
                    if len(module_parts) >= 2:
                        category = module_parts[1].title()
                
                categories.setdefault(category, []).append(command)
        
        return categories
    
    def _get_category_emoji(self, category: str) -> str:
        """Get emoji cho từng category"""
        emoji_map = {
            "Moderation": "🛡️",
            "Utilities": "🔧",
            "Core": "⚙️",
            "Interactions": "🖱️",
            "Fun": "🎮",
            "Info": "📊",
            "Other": "📦"
        }
        return emoji_map.get(category, "📌")
    
    def _get_category_description(self, category: str) -> str:
        """Get description cho từng category"""
        desc_map = {
            "Moderation": "Quản lý server và members",
            "Utilities": "Công cụ tiện ích",
            "Core": "Lệnh cốt lõi của bot",
            "Interactions": "Context menus và modals",
            "Fun": "Giải trí",
            "Info": "Thông tin",
            "Other": "Các lệnh khác"
        }
        return desc_map.get(category, "Miscellaneous commands")
    
    @app_commands.command(name="help", description="Hiển thị tất cả commands của bot")
    @app_commands.describe(command="Tên command cần xem chi tiết (optional)")
    async def help(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None
    ):
        """Dynamic help command"""
        try:
            if command:
                await self._show_command_help(interaction, command)
                return
            
            categories = self._get_command_categories()
            
            if not categories:
                await interaction.response.send_message(
                    embed=info_embed("Không có commands nào được tìm thấy!"),
                    ephemeral=True
                )
                return
            
            embed = create_embed(
                title=f"{EMOJIS.get('bot', '🤖')} Danh sách Commands",
                description=f"Bot hiện có **{sum(len(cmds) for cmds in categories.values())} commands** trong **{len(categories)} categories**\n\n"
                           f"Sử dụng `/help <command>` để xem chi tiết một command.",
                color=COLORS['primary']
            )
            
            for category, cmds in sorted(categories.items()):
                emoji = self._get_category_emoji(category)
                desc = self._get_category_description(category)
                
                command_list = []
                for cmd in sorted(cmds, key=lambda x: x.qualified_name):
                    cmd_desc = getattr(cmd, 'description', None) or "No description"
                    command_list.append(f"`/{cmd.qualified_name}` - {cmd_desc}")
                
                if command_list:
                    embed.add_field(
                        name=f"{emoji} {category} ({len(cmds)})",
                        value=f"*{desc}*\n" + "\n".join(command_list[:5]),
                        inline=False
                    )
                    
                    if len(command_list) > 5:
                        for i in range(5, len(command_list), 5):
                            embed.add_field(
                                name="⠀",
                                value="\n".join(command_list[i:i+5]),
                                inline=False
                            )
            
            total_cmds = sum(len(cmds) for cmds in categories.values())
            embed.set_footer(
                text=f"Tổng cộng {total_cmds} commands • Sử dụng /help <command> để xem chi tiết"
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.logger.info(f"{interaction.user} đã xem danh sách help")
            
        except Exception as e:
            self.logger.error(f"Error in help command: {e}", exc_info=True)
            await interaction.response.send_message(
                embed=info_embed(f"Lỗi: {str(e)}"),
                ephemeral=True
            )
    
    async def _show_command_help(self, interaction: discord.Interaction, command_name: str):
        """Hiển thị chi tiết một command"""
        cmd = None
        for command in self.bot.tree.walk_commands():
            if isinstance(command, app_commands.Command) and command.qualified_name == command_name:
                cmd = command
                break
        
        if not cmd:
            await interaction.response.send_message(
                embed=info_embed(
                    f"Command `{command_name}` không tồn tại!",
                    "Sử dụng `/help` để xem danh sách tất cả commands."
                ),
                ephemeral=True
            )
            return
        
        embed = create_embed(
            title=f"📖 Command: /{cmd.qualified_name}",
            description=getattr(cmd, 'description', None) or "Không có mô tả",
            color=COLORS['info']
        )
        
        parameters = getattr(cmd, 'parameters', [])
        if parameters:
            params_text = []
            for param in parameters:
                required = "**Required**" if getattr(param, 'required', False) else "*Optional*"
                param_desc = getattr(param, 'description', None) or "No description"
                param_name = getattr(param, 'name', 'param')
                params_text.append(f"• `{param_name}` ({required}): {param_desc}")
            
            embed.add_field(
                name="⚙️ Parameters",
                value="\n".join(params_text),
                inline=False
            )
        else:
            embed.add_field(
                name="⚙️ Parameters",
                value="*Command này không có parameters*",
                inline=False
            )
        
        param_names = " ".join([f"<{getattr(p, 'name', 'p')}>" if getattr(p, 'required', False) else f"[{getattr(p, 'name', 'p')}]" for p in parameters])
        usage = f"`/{cmd.qualified_name} {param_names.strip()}`" if param_names else f"`/{cmd.qualified_name}`"
        
        embed.add_field(
            name="💡 Cách dùng",
            value=usage,
            inline=False
        )
        
        default_perms = getattr(cmd, 'default_permissions', None)
        if default_perms:
            try:
                perms = [
                    name.replace('_', ' ').title()
                    for name, value in default_perms
                    if value
                ]
                if perms:
                    embed.add_field(
                        name="🔐 Permissions Required",
                        value=", ".join(perms),
                        inline=False
                    )
            except Exception:
                pass
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.logger.info(f"{interaction.user} đã xem help cho command {command_name}")
    
    async def cog_unload(self):
        return


async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
