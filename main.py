import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import logging
from pathlib import Path

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('BlastBot')


class BlastBot(commands.Bot):
    """Main bot class với custom initialization"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=os.getenv('BOT_PREFIX', '!'),
            intents=intents,
            help_command=None  # Disable default help command
        )
        
        # Auto-discover extensions from cogs folder
        self.initial_extensions = self._discover_extensions()
    
    def _discover_extensions(self) -> list[str]:
        """Tự động tìm và load tất cả cog modules"""
        extensions = []
        cogs_path = Path(__file__).parent / 'cogs'
        
        if not cogs_path.exists():
            logger.warning("Thư mục cogs không tồn tại!")
            return extensions
        
        # Scan thư mục cogs
        for item in cogs_path.iterdir():
            # Bỏ qua __pycache__ và hidden files
            if item.name.startswith('_') or item.name.startswith('.'):
                continue
            
            # Nếu là thư mục và có __init__.py -> là module
            if item.is_dir():
                init_file = item / '__init__.py'
                if init_file.exists():
                    module_name = f'cogs.{item.name}'
                    extensions.append(module_name)
                    logger.debug(f"Tìm thấy module: {module_name}")
            
            # Nếu là file .py (không phải __init__.py) -> là single cog
            elif item.is_file() and item.suffix == '.py' and item.stem != '__init__':
                module_name = f'cogs.{item.stem}'
                extensions.append(module_name)
                logger.debug(f"Tìm thấy cog: {module_name}")
        
        logger.info(f"Đã phát hiện {len(extensions)} extensions: {', '.join(extensions)}")
        return extensions
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info("Đang tải extensions...")
        
        # Set up tree error handler
        self.tree.on_error = self.on_app_command_error
        
        # Load all cogs
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"✅ Đã tải {ext}")
            except Exception as e:
                logger.error(f"❌ Không thể tải {ext}: {e}")
        
        # Sync commands (global hoặc guild-specific cho testing)
        guild_id = os.getenv('GUILD_ID')
        if guild_id:
            # Sync to specific guild for faster testing
            guild = discord.Object(id=int(guild_id))
            
            # Clear old commands trước khi sync mới
            self.tree.clear_commands(guild=guild)
            self.tree.copy_global_to(guild=guild)
            
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Đã sync {len(synced)} commands cho guild {guild_id}")
        else:
            # Sync globally (có thể mất ~1 giờ để update)
            # Clear old commands
            self.tree.clear_commands(guild=None)
            synced = await self.tree.sync()
            logger.info(f"Đã sync {len(synced)} commands globally")
    
    async def on_ready(self):
        """Called when bot is ready"""
        if self.user:
            logger.info(f"🚀 Bot đã sẵn sàng! Đăng nhập với tên: {self.user.name}")
        logger.info(f"📊 Đang hoạt động trên {len(self.guilds)} servers")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="your server"
            )
        )
    
    async def close(self):
        """Graceful shutdown"""
        logger.info("🛑 Đang tắt bot...")
        
        # Close database connections if exists
        try:
            from utils.database import Database
            # Database cleanup would go here if needed
            logger.info("✅ Đã cleanup resources")
        except Exception as e:
            logger.error(f"❌ Lỗi khi cleanup: {e}")
        
        # Call parent close
        await super().close()
        logger.info("✅ Bot đã tắt hoàn toàn")
    
    async def on_command_error(self, ctx, error):
        """Global error handler for prefix commands"""
        if isinstance(error, commands.CommandNotFound):
            return
        logger.error(f"Command error: {error}")
    
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError
    ):
        """Global error handler for slash commands"""
        from utils.error_handler import handle_command_error
        
        # Handle CommandNotFound separately (cache issue)
        if isinstance(error, discord.app_commands.CommandNotFound):
            logger.warning(
                f"Command '{error.name}' không tồn tại nhưng vẫn được gọi bởi {interaction.user}. "
                f"Discord đang cache command cũ. Đã tự động clear trong lần sync tiếp theo."
            )
            try:
                await interaction.response.send_message(
                    "⚠️ Lệnh này đã bị xóa. Vui lòng reload Discord (Ctrl+R) để cập nhật danh sách lệnh.",
                    ephemeral=True
                )
            except (discord.InteractionResponded, discord.HTTPException):
                pass
            return
        
        # Unwrap the error if it's wrapped
        original_error = getattr(error, 'original', error)
        
        await handle_command_error(interaction, original_error)


async def main():
    """Main entry point"""
    # Check for token
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ Không tìm thấy DISCORD_TOKEN trong file .env!")
        logger.error("Vui lòng tạo file .env và thêm token của bạn.")
        return
    
    # Create data directory if not exists
    Path('data').mkdir(exist_ok=True)
    
    # Start bot
    bot = BlastBot()
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("⚠️ Nhận tín hiệu KeyboardInterrupt (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Lỗi khi chạy bot: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("✅ Bot đã được tắt bởi người dùng")
    except Exception as e:
        logger.error(f"❌ Lỗi nghiêm trọng: {e}", exc_info=True)
