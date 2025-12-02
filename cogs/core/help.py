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
        # Cache for command categories
        self._categories_cache: Optional[dict[str, list[app_commands.Command]]] = None
        self._cache_version = 0
    
    def _invalidate_cache(self):
        """Invalidate command categories cache"""
        self._categories_cache = None
        self._cache_version += 1
        self.logger.debug("Invalidated help command cache")
    
    def _get_command_categories(self) -> dict[str, list[app_commands.Command]]:
        """Tự động phân loại commands theo cog/module (with caching)"""
        # Return cached version if available
        if self._categories_cache is not None:
            self.logger.debug("Using cached command categories")
            return self._categories_cache
        
        categories = {}
        
        # Get all app commands from tree
        for command in self.bot.tree.walk_commands():
            if isinstance(command, app_commands.Command):
                # Lấy category từ cog hoặc module name
                cog_name = command.binding.__class__.__name__ if command.binding else "Other"
                
                # Parse module path để lấy category name
                if hasattr(command.binding, '__module__'):
                    module_parts = command.binding.__module__.split('.')
                    if len(module_parts) >= 2:
                        # cogs.moderation.kick -> Moderation
                        category = module_parts[1].title()
                    else:
                        category = "Other"
                else:
                    category = "Other"
                
                if category not in categories:
                    categories[category] = []
                
                categories[category].append(command)
        
        # Cache the result
        self._categories_cache = categories
        self.logger.debug(f"Cached {len(categories)} command categories")
        
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
            # Nếu có command cụ thể
            if command:
                await self._show_command_help(interaction, command)
                return
            
            # Hiển thị tất cả commands
            categories = self._get_command_categories()
            
            if not categories:
                await interaction.response.send_message(
                    embed=info_embed("Không có commands nào được tìm thấy!"),
                    ephemeral=True
                )
                return
            
            # Tạo embed
            embed = create_embed(
                title=f"{EMOJIS.get('bot', '🤖')} Danh sách Commands",
                description=f"Bot hiện có **{sum(len(cmds) for cmds in categories.values())} commands** trong **{len(categories)} categories**\n\n"
                           f"Sử dụng `/help <command>` để xem chi tiết một command.",
                color=COLORS['primary']
            )
            
            # Thêm từng category
            for category, cmds in sorted(categories.items()):
                emoji = self._get_category_emoji(category)
                desc = self._get_category_description(category)
                
                command_list = []
                for cmd in sorted(cmds, key=lambda x: x.name):
                    # Format: /command - description
                    cmd_desc = cmd.description or "No description"
                    command_list.append(f"`/{cmd.name}` - {cmd_desc}")
                
                if command_list:
                    embed.add_field(
                        name=f"{emoji} {category} ({len(cmds)})",
                        value=f"*{desc}*\n" + "\n".join(command_list[:5]),  # Limit 5 per field
                        inline=False
                    )
                    
                    # Nếu có nhiều hơn 5, thêm field khác
                    if len(command_list) > 5:
                        for i in range(5, len(command_list), 5):
                            embed.add_field(
                                name="⠀",  # Zero-width space
                                value="\n".join(command_list[i:i+5]),
                                inline=False
                            )
            
            # Footer với thông tin
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
        # Tìm command
        cmd = None
        for command in self.bot.tree.walk_commands():
            if isinstance(command, app_commands.Command) and command.name == command_name:
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
        
        # Tạo embed chi tiết
        embed = create_embed(
            title=f"📖 Command: /{cmd.name}",
            description=cmd.description or "Không có mô tả",
            color=COLORS['info']
        )
        
        # Parameters
        if cmd.parameters:
            params_text = []
            for param in cmd.parameters:
                required = "**Required**" if param.required else "*Optional*"
                param_desc = param.description or "No description"
                params_text.append(f"• `{param.name}` ({required}): {param_desc}")
            
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
        
        # Usage example
        param_names = " ".join([f"<{p.name}>" if p.required else f"[{p.name}]" for p in cmd.parameters])
        usage = f"`/{cmd.name} {param_names.strip()}`" if param_names else f"`/{cmd.name}`"
        
        embed.add_field(
            name="💡 Cách dùng",
            value=usage,
            inline=False
        )
        
        # Permissions
        if hasattr(cmd, '_default_permissions') and cmd.default_permissions:
            perms = []
            for perm, value in cmd.default_permissions:
                if value:
                    perms.append(perm.replace('_', ' ').title())
            
            if perms:
                embed.add_field(
                    name="🔐 Permissions Required",
                    value=", ".join(perms),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.logger.info(f"{interaction.user} đã xem help cho command {command_name}")
    
    async def cog_unload(self):
        """Cleanup khi cog unload"""
        self._invalidate_cache()


async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
