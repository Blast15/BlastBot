"""Context Menus - Right-click actions"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timedelta
from utils.embeds import user_info_embed, create_embed, success_embed
from utils.constants import COLORS
from utils.modals import ReportModal

logger = logging.getLogger('BlastBot.ContextMenus')


class ContextMenus(commands.Cog):
    """Context menus cho users và messages"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('BlastBot.ContextMenus')
        self._temp_report_messages: dict[int, dict] = {}  # Local cache instead of bot attribute
        self._cleanup_task = None
        
        # Register context menus
        self.user_info_menu = app_commands.ContextMenu(
            name="Thông tin User",
            callback=self.user_info_context
        )
        self.bot.tree.add_command(self.user_info_menu)
        
        self.report_user_menu = app_commands.ContextMenu(
            name="Báo cáo User",
            callback=self.report_user_context
        )
        self.bot.tree.add_command(self.report_user_menu)
        
        self.get_avatar_menu = app_commands.ContextMenu(
            name="Xem Avatar",
            callback=self.get_avatar_context
        )
        self.bot.tree.add_command(self.get_avatar_menu)
        
        self.report_message_menu = app_commands.ContextMenu(
            name="Báo cáo Message",
            callback=self.report_message_context
        )
        self.bot.tree.add_command(self.report_message_menu)
        
        self.bookmark_message_menu = app_commands.ContextMenu(
            name="Bookmark Message",
            callback=self.bookmark_message_context
        )
        self.bot.tree.add_command(self.bookmark_message_menu)
        
        # Start cleanup task
        self._cleanup_task = self.bot.loop.create_task(self._cleanup_temp_messages())
    
    async def cog_unload(self):
        """Cleanup khi unload cog"""
        self.bot.tree.remove_command(self.user_info_menu.name, type=self.user_info_menu.type)
        self.bot.tree.remove_command(self.report_user_menu.name, type=self.report_user_menu.type)
        self.bot.tree.remove_command(self.get_avatar_menu.name, type=self.get_avatar_menu.type)
        self.bot.tree.remove_command(self.report_message_menu.name, type=self.report_message_menu.type)
        self.bot.tree.remove_command(self.bookmark_message_menu.name, type=self.bookmark_message_menu.type)
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Clear temp data
        self._temp_report_messages.clear()
    
    async def _cleanup_temp_messages(self):
        """Background task to cleanup old temp message data"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                # Remove entries older than 1 hour
                current_time = datetime.utcnow()
                to_remove = []
                
                for msg_id, data in self._temp_report_messages.items():
                    timestamp = data.get('timestamp', current_time)
                    if current_time - timestamp > timedelta(hours=1):
                        to_remove.append(msg_id)
                
                for msg_id in to_remove:
                    del self._temp_report_messages[msg_id]
                
                if to_remove:
                    self.logger.debug(f"Cleaned up {len(to_remove)} old temp message entries")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}", exc_info=True)
    
    async def user_info_context(self, interaction: discord.Interaction, user: discord.User):
        """Context menu: Xem thông tin user"""
        target = user
        
        # Nếu trong guild, lấy member object
        if interaction.guild:
            try:
                target = await interaction.guild.fetch_member(user.id)
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                self.logger.warning(f"Failed to fetch member {user.id}: {e}")
        
        embed = user_info_embed(target)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.logger.info(f"{interaction.user} viewed info for {user}")
    
    async def report_user_context(self, interaction: discord.Interaction, user: discord.User):
        """Context menu: Báo cáo user"""
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ Bạn không thể báo cáo chính mình!",
                ephemeral=True
            )
            return
        
        if user.bot:
            await interaction.response.send_message(
                "❌ Không thể báo cáo bot!",
                ephemeral=True
            )
            return
        
        # Mở modal để nhập lý do
        modal = ReportModal(target_id=user.id, target_type="user")
        await interaction.response.send_modal(modal)
        self.logger.info(f"{interaction.user} reporting user {user}")
    
    async def get_avatar_context(self, interaction: discord.Interaction, user: discord.User):
        """Context menu: Xem avatar"""
        embed = create_embed(
            title=f"Avatar của {user.display_name}",
            color=COLORS['primary']
        )
        embed.set_image(url=user.display_avatar.url)
        
        # Thêm button download
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Tải xuống",
                url=user.display_avatar.url
            )
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        self.logger.info(f"{interaction.user} viewed avatar of {user}")
    
    async def report_message_context(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu: Báo cáo message"""
        if message.author.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ Bạn không thể báo cáo tin nhắn của chính mình!",
                ephemeral=True
            )
            return
        
        if message.author.bot:
            await interaction.response.send_message(
                "❌ Không thể báo cáo tin nhắn của bot!",
                ephemeral=True
            )
            return
        
        # Mở modal với context về message
        modal = ReportModal(target_id=message.id, target_type="message")
        
        # Store message info để reference sau (with timestamp for cleanup)
        self._temp_report_messages[message.id] = {
            'author': message.author.id,
            'channel': message.channel.id,
            'jump_url': message.jump_url,
            'content': message.content[:100],  # First 100 chars
            'timestamp': datetime.utcnow()
        }
        
        await interaction.response.send_modal(modal)
        self.logger.info(f"{interaction.user} reporting message {message.id} from {message.author}")
    
    async def bookmark_message_context(self, interaction: discord.Interaction, message: discord.Message):
        """Context menu: Bookmark message để xem sau"""
        # Get channel info safely
        if isinstance(message.channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            channel_info = message.channel.mention
        else:
            channel_info = f"#{getattr(message.channel, 'name', 'Unknown')}"
        
        embed = create_embed(
            title="📌 Message đã được bookmark",
            description=f"**Từ:** {message.author.mention}\n"
                       f"**Channel:** {channel_info}\n"
                       f"**Nội dung:**\n{message.content[:500] if message.content else '*Không có text*'}",
            color=COLORS['info']
        )
        
        # Thêm jump link button
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Đi đến tin nhắn",
                url=message.jump_url,
                emoji="🔗"
            )
        )
        
        # Gửi bookmark qua DM
        try:
            await interaction.user.send(embed=embed, view=view)
            await interaction.response.send_message(
                embed=success_embed(
                    "Đã bookmark!",
                    "Message đã được gửi vào DM của bạn."
                ),
                ephemeral=True
            )
            self.logger.info(f"{interaction.user} bookmarked message {message.id}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Không thể gửi DM cho bạn! Vui lòng bật DM từ server members.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(ContextMenus(bot))
