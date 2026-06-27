"""Base classes và utilities cho moderation commands"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Tuple
import logging
import aiosqlite
from utils.embeds import error_embed
from utils.constants import MESSAGES
from utils.error_handler import validate_number_range, ValidationError


def require_guild_permissions(**perms):
    """Decorator check permissions của user trước khi callback chạy."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            raise app_commands.CheckFailure("Không thể xác định được member!")
        missing = [p for p, val in perms.items() if val and not getattr(interaction.user.guild_permissions, p, False)]
        if missing:
            raise app_commands.MissingPermissions(missing)
        return True
    return app_commands.check(predicate)


class BaseModerationCog(commands.Cog):
    """Base class cho tất cả moderation cogs với shared functionality"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger(f'BlastBot.Moderation.{self.__class__.__name__}')
    
    async def validate_hierarchy(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        action: str = "thực hiện hành động này"
    ) -> Tuple[bool, Optional[str]]:
        """Validate hierarchy cho moderation actions"""
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
        bot_member = interaction.guild.get_member(self.bot.user.id) if self.bot.user else None
        if bot_member and target.top_role >= bot_member.top_role:
            return False, f"Bot không thể {action} với member có role cao hơn hoặc bằng bot!"
        
        return True, None
    
    async def validate_target(
        self,
        interaction: discord.Interaction,
        target: discord.Member
    ) -> Tuple[bool, Optional[str]]:
        """Validate target member"""
        if target.id == interaction.user.id:
            return False, "Bạn không thể thực hiện hành động này với chính mình!"
        
        if target.bot:
            return False, "Không thể thực hiện hành động này với bot!"
        
        if interaction.guild and target.id == interaction.guild.owner_id:
            return False, "Không thể thực hiện hành động này với server owner!"
        
        return True, None
    
    async def send_error(
        self,
        interaction: discord.Interaction,
        message: str,
        use_followup: bool = False
    ):
        """Send error message"""
        embed = error_embed("Lỗi", message)
        
        if use_followup or interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    async def safe_error_response(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str
    ):
        """Gửi lỗi an toàn dù interaction đã defer hay chưa."""
        embed = error_embed(title, description)
        try:
            if interaction.response.is_done():
                try:
                    await interaction.edit_original_response(embed=embed, view=None)
                except discord.HTTPException:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException as e:
            self.logger.error(f"Không thể gửi error response: {e}")

    async def try_dm_member(self, member: discord.Member, embed: discord.Embed) -> bool:
        try:
            await member.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False
    
    async def log_moderation_action(
        self,
        guild: discord.Guild,
        moderator: discord.Member | discord.User,
        action: str,
        target: discord.abc.User | None = None,
        reason: str | None = None,
        extra_info: Optional[str] = None,
        **extra
    ):
        """Log moderation action vào log channel"""
        from utils.embeds import create_embed
        from utils.constants import COLORS
        
        try:
            db = getattr(self.bot, 'db', None)
            if db is None:
                if hasattr(self.bot, 'logger'):
                    self.bot.logger.warning("log_moderation_action gọi khi DB chưa sẵn sàng")
                return

            target_id = target.id if target is not None else 0
            target_str = str(target) if target is not None else None

            await db.add_mod_log(
                guild_id=guild.id,
                moderator_id=moderator.id,
                action=action,
                target_id=target_id,
                target_str=target_str,
                reason=reason,
                **extra,
            )

            config = await db.get_guild_config(guild.id)
            
            if not config.get('log_channel_id'):
                return
            
            log_channel = guild.get_channel(config['log_channel_id'])
            if not log_channel or not isinstance(log_channel, (discord.TextChannel, discord.Thread)):
                return
            
            embed = create_embed(
                title=f"🛡️ Moderation Action: {action.title()}",
                description=f"**Moderator:** {moderator.mention} (`{moderator.id}`)\n"
                           f"**Reason:** {reason or 'Không có lý do'}",
                color=COLORS['warning']
            )

            if target_str:
                embed.add_field(name="Target", value=target_str, inline=True)
            
            if extra_info:
                embed.add_field(name="Extra Info", value=extra_info, inline=False)
            
            embed.set_footer(text="Action performed at")
            embed.timestamp = discord.utils.utcnow()
            
            await log_channel.send(embed=embed)
            
        except (aiosqlite.Error, discord.HTTPException) as e:
            self.logger.error(f"Failed to log moderation action: {e}", exc_info=True)


def validate_duration(duration: int, min_val: int, max_val: int) -> Tuple[bool, Optional[str]]:
    try:
        validate_number_range(duration, min_val, max_val, "Thời gian")
        return True, None
    except ValidationError as e:
        return False, e.user_message


def validate_amount(amount: int, min_val: int = 1, max_val: int = 100) -> Tuple[bool, Optional[str]]:
    try:
        validate_number_range(amount, min_val, max_val, "Số lượng")
        return True, None
    except ValidationError as e:
        return False, e.user_message
