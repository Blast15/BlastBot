import discord
from discord.ext import commands
from typing import Optional, Dict, List
import math

class Help(commands.Cog):
    """A cog that provides help command functionality for the bot."""
    
    def __init__(self, bot):
        self.bot = bot
        self.emoji_map = {
            'moderation': '🛡️',
            'random': '🎲',
            'sync': '🔄',
            'help': '❓',
            'owner': '👑',
            'config': '⚙️',
            'utility': '🔧',
            'fun': '🎮',
            'music': '🎵',
            'economy': '💰',
            'leveling': '📈',
            'giveaway': '🎁',
            'info': 'ℹ️',
        }
        self.color = 0x2F3136
        # Command categories (mapping cog names to user-friendly names)
        self.categories = {
            'moderation': 'Quản lý Server',
            'random': 'Giải trí',
            'sync': 'Cấu hình',
            'help': 'Trợ giúp',
        }

    def get_command_signature(self, command: commands.Command) -> str:
        """Get the properly formatted command signature with prefix and arguments."""
        return f"{command.name} {command.signature}"
        
    def get_cog_emoji(self, cog_name: str) -> str:
        """Get the emoji for a specific cog name."""
        return self.emoji_map.get(cog_name.lower(), '📁')
        
    def get_category_name(self, cog_name: str) -> str:
        """Get user-friendly category name from cog name."""
        return self.categories.get(cog_name.lower(), cog_name)

    def group_commands_by_cog(self) -> Dict[str, List[commands.Command]]:
        """Group all commands by their cog, filtering out hidden commands."""
        grouped_commands = {}
        
        for command in self.bot.commands:
            if command.hidden:
                continue
                
            cog_name = command.cog.qualified_name if command.cog else "No Category"
            
            if cog_name not in grouped_commands:
                grouped_commands[cog_name] = []
                
            grouped_commands[cog_name].append(command)
            
        # Also check hybrid commands from the app_commands tree
        for command in self.bot.tree.get_commands():
            if isinstance(command, discord.app_commands.Command) and hasattr(command, 'binding'):
                cog_name = command.binding.qualified_name if command.binding else "No Category"
                
                if cog_name not in grouped_commands:
                    grouped_commands[cog_name] = []
                
                # Check if this command is already in the list
                cmd_names = [cmd.name for cmd in grouped_commands[cog_name]]
                if command.name not in cmd_names:
                    grouped_commands[cog_name].append(command)
                
        return grouped_commands

    @commands.hybrid_command(name="help", description="Hiển thị trợ giúp về các lệnh")
    async def help(self, ctx: commands.Context, command: Optional[str] = None) -> None:
        """Help command to display available commands and their usage."""
        
        prefix = await self.bot.get_prefix(ctx.message)
        if isinstance(prefix, list):
            prefix = prefix[0]
            
        if command:
            # Hiển thị trợ giúp chi tiết cho một lệnh cụ thể
            cmd = self.bot.get_command(command)
            if not cmd:
                await ctx.send(embed=discord.Embed(
                    description="❌ Không tìm thấy lệnh này!",
                    color=0xE02B2B
                ))
                return

            embed = discord.Embed(
                title=f"{self.get_cog_emoji(cmd.cog_name) if cmd.cog else '📝'} `{cmd.name}` - Thông tin chi tiết",
                description=cmd.description or "Không có mô tả",
                color=self.color
            )

            # Hiển thị các cách gọi lệnh (Slash và Prefix)
            usage_text = f"**Slash Command:** `/{cmd.name}`\n"
            if cmd.signature:
                usage_text += f"**Prefix Command:** `{prefix}{self.get_command_signature(cmd)}`"
            else:
                usage_text += f"**Prefix Command:** `{prefix}{cmd.name}`"
                
            embed.add_field(name="📋 Cách sử dụng", value=usage_text, inline=False)
            
            # Thêm các tên khác nếu có
            if cmd.aliases:
                embed.add_field(
                    name="🏷️ Tên khác", 
                    value=", ".join([f"`{prefix}{alias}`" for alias in cmd.aliases]), 
                    inline=False
                )
            
            # Thêm phân loại
            if cmd.cog:
                embed.add_field(
                    name="📁 Phân loại", 
                    value=self.get_category_name(cmd.cog_name), 
                    inline=True
                )
            
            # Thêm cooldown nếu có
            if cmd._buckets and cmd._buckets._cooldown:
                cooldown = cmd._buckets._cooldown
                embed.add_field(
                    name="⏱️ Cooldown", 
                    value=f"{cooldown.rate} lần mỗi {cooldown.per:.0f} giây", 
                    inline=True
                )
            
            # Thêm các lưu ý về quyền hạn
            required_permissions = []
            
            for check in cmd.checks:
                if hasattr(check, "__qualname__") and "has_permissions" in check.__qualname__:
                    required_permissions.extend([
                        perm.replace('_', ' ').title() 
                        for perm, value in check.kwargs.items() 
                        if value
                    ])
            
            if required_permissions:
                embed.add_field(
                    name="🔒 Yêu cầu quyền", 
                    value=", ".join(required_permissions), 
                    inline=False
                )

        else:
            # Hiển thị tổng quan các lệnh theo nhóm
            embed = discord.Embed(
                title="📚 Trợ giúp Blast Bot",
                description=f"Sử dụng `{prefix}help <lệnh>` để xem thông tin chi tiết về một lệnh cụ thể.",
                color=self.color
            )
            
            # Phân nhóm lệnh theo cog
            grouped_commands = self.group_commands_by_cog()
            
            # Sắp xếp các nhóm và thêm vào embed
            for cog_name, commands_list in sorted(grouped_commands.items()):
                if not commands_list:  # Bỏ qua nhóm không có lệnh
                    continue
                
                # Lấy emoji và tên thân thiện cho nhóm
                emoji = self.get_cog_emoji(cog_name)
                category_name = self.get_category_name(cog_name)
                
                # Tạo danh sách lệnh trong nhóm
                commands_text = ""
                for cmd in sorted(commands_list, key=lambda x: x.name):
                    desc = cmd.description.split('\n')[0] if cmd.description else "Không có mô tả"
                    if len(desc) > 50:
                        desc = desc[:50] + "..."
                    commands_text += f"`{cmd.name}` - {desc}\n"
                
                embed.add_field(
                    name=f"{emoji} {category_name}",
                    value=commands_text,
                    inline=False
                )

        embed.set_footer(text=f"Dùng {prefix}help <lệnh> để xem chi tiết về một lệnh")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
