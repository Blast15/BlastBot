"""Base classes và utilities cho moderation commands"""

import discord
from discord.ext import commands
from typing import Optional, Tuple
import logging
from utils.embeds import error_embed
from utils.constants import MESSAGES


class BaseModerationCog(commands.Cog):
    """Base class cho tất cả moderation cogs với shared functionality"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f'BlastBot.Moderation.{self.__class__.__name__}')
    
    async def validate_permissions(
        self,
        interaction: discord.Interaction,
        required_permission: str
    ) -> bool:
        """
        Validate user có permission cần thiết
        
        Args:
            interaction: Discord interaction
            required_permission: Tên permission cần check (e.g., 'kick_members')
        
        Returns:
            bool: True nếu có permission, False nếu không
        """
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Lỗi", "Không thể xác định member!"),
                ephemeral=True
            )
            return False
        
        if not getattr(interaction.user.guild_permissions, required_permission, False):
            await interaction.response.send_message(
                embed=error_embed("Lỗi", MESSAGES['errors']['missing_permissions']),
                ephemeral=True
            )
            return False
        
        return True
    
    async def validate_hierarchy(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        action: str = "thực hiện hành động này"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate hierarchy cho moderation actions
        
        Args:
            interaction: Discord interaction
            target: Target member
            action: Tên hành động (for error message)
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not isinstance(interaction.user, discord.Member):
            return False, "Không thể xác định moderator!"
        
        if not interaction.guild:
            return False, "Không thể xác định guild!"
        
        # Check if target is bot owner or admin
        if target.guild_permissions.administrator and not interaction.user.guild_permissions.administrator:
            return False, f"Bạn không thể {action} với administrator!"
        
        # Check moderator hierarchy
        if target.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            return False, f"Bạn không thể {action} với member có role cao hơn hoặc bằng bạn!"
        
        # Check bot hierarchy
        bot_member = interaction.guild.get_member(self.bot.user.id)
        if bot_member and target.top_role >= bot_member.top_role:
            return False, f"Bot không thể {action} với member có role cao hơn hoặc bằng bot!"
        
        return True, None
    
    async def validate_target(
        self,
        interaction: discord.Interaction,
        target: discord.Member
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate target member (không phải bản thân, không phải bot, etc.)
        
        Args:
            interaction: Discord interaction
            target: Target member
        
        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        # Không thể target chính mình
        if target.id == interaction.user.id:
            return False, "Bạn không thể thực hiện hành động này với chính mình!"
        
        # Không thể target bot
        if target.bot:
            return False, "Không thể thực hiện hành động này với bot!"
        
        # Không thể target server owner
        if interaction.guild and target.id == interaction.guild.owner_id:
            return False, "Không thể thực hiện hành động này với server owner!"
        
        return True, None
    
    async def send_error(
        self,
        interaction: discord.Interaction,
        message: str,
        use_followup: bool = False
    ):
        """
        Send error message (handle both response and followup)
        
        Args:
            interaction: Discord interaction
            message: Error message
            use_followup: Dùng followup thay vì response
        """
        embed = error_embed("Lỗi", message)
        
        if use_followup or interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def log_moderation_action(
        self,
        guild: discord.Guild,
        moderator: discord.Member | discord.User,
        action: str,
        target: discord.Member | discord.User,
        reason: str,
        extra_info: Optional[str] = None
    ):
        """
        Log moderation action vào log channel nếu có
        
        Args:
            guild: Guild where action occurred
            moderator: Moderator who performed action
            action: Action type (kick, ban, timeout, etc.)
            target: Target member
            reason: Reason for action
            extra_info: Extra info to log (optional)
        """
        from utils.database import Database
        from utils.embeds import create_embed
        from utils.constants import COLORS
        
        try:
            # Get log channel từ database
            db = Database()
            await db.connect()
            config = await db.get_guild_config(guild.id)
            await db.close()
            
            if not config.get('log_channel_id'):
                return
            
            log_channel = guild.get_channel(config['log_channel_id'])
            if not log_channel or not isinstance(log_channel, (discord.TextChannel, discord.Thread)):
                return
            
            # Tạo log embed
            embed = create_embed(
                title=f"🛡️ Moderation Action: {action.title()}",
                description=f"**Moderator:** {moderator.mention} (`{moderator.id}`)\n"
                           f"**Target:** {target.mention} (`{target.id}`)\n"
                           f"**Reason:** {reason}",
                color=COLORS['warning']
            )
            
            if extra_info:
                embed.add_field(name="Extra Info", value=extra_info, inline=False)
            
            embed.set_footer(text=f"Action performed at")
            embed.timestamp = discord.utils.utcnow()
            
            await log_channel.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Failed to log moderation action: {e}", exc_info=True)


# Shared validation functions (can be used outside of class)

def validate_duration(duration: int, min_val: int, max_val: int) -> Tuple[bool, Optional[str]]:
    """
    Validate duration value
    
    Args:
        duration: Duration value
        min_val: Minimum allowed value
        max_val: Maximum allowed value
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if duration < min_val or duration > max_val:
        return False, f"Giá trị phải từ {min_val} đến {max_val}!"
    
    return True, None


def validate_amount(amount: int, min_val: int = 1, max_val: int = 100) -> Tuple[bool, Optional[str]]:
    """
    Validate amount value (for clear command, etc.)
    
    Args:
        amount: Amount value
        min_val: Minimum allowed value
        max_val: Maximum allowed value
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if amount < min_val or amount > max_val:
        return False, f"Số lượng phải từ {min_val} đến {max_val}!"
    
    return True, None
