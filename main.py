import discord
from discord.ext import commands, tasks
import asyncio
import os
from dotenv import load_dotenv
import logging
from pathlib import Path
from datetime import datetime

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
        
        # Thời gian khởi động bot
        self.start_time = None
        
        # Task tự động restart
        self.auto_restart_task = None
    
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
        
        # Lưu thời gian khởi động
        self.start_time = datetime.now()
        logger.info(f"⏰ Bot khởi động lúc: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Bắt đầu task tự động restart nếu chưa chạy
        if self.auto_restart_task is None or self.auto_restart_task.done():
            self.auto_restart_task = asyncio.create_task(self._auto_restart_loop())
            logger.info("✅ Đã kích hoạt tính năng tự động khởi động lại mỗi 12 tiếng")
        
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
        
        # Hủy task tự động restart nếu đang chạy
        if self.auto_restart_task and not self.auto_restart_task.done():
            self.auto_restart_task.cancel()
            logger.info("✅ Đã hủy task tự động khởi động lại")
        
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
    
    async def _auto_restart_loop(self):
        """Background task để tự động restart bot mỗi 12 tiếng"""
        try:
            # Chờ 12 tiếng (43200 giây)
            RESTART_INTERVAL = 12 * 60 * 60  # 12 giờ
            
            while True:
                await asyncio.sleep(RESTART_INTERVAL)
                
                # Log thông tin trước khi restart
                uptime = datetime.now() - self.start_time if self.start_time else None
                logger.info("=" * 50)
                logger.info("🔄 Đã đến thời gian tự động khởi động lại bot")
                if uptime:
                    logger.info(f"⏱️ Uptime: {uptime}")
                logger.info("=" * 50)
                
                # Gửi thông báo trước khi restart (nếu có owner được cấu hình)
                await self._notify_before_restart()
                
                # Đóng bot và trigger restart
                await self.close()
                
        except asyncio.CancelledError:
            logger.info("⚠️ Task tự động khởi động lại đã bị hủy")
        except Exception as e:
            logger.error(f"❌ Lỗi trong task tự động khởi động lại: {e}", exc_info=True)
    
    async def _notify_before_restart(self):
        """Gửi thông báo cho owner trước khi restart (tùy chọn)"""
        try:
            owner_id = os.getenv('OWNER_ID')
            if owner_id:
                owner = await self.fetch_user(int(owner_id))
                if owner:
                    await owner.send(
                        "🔄 Bot sẽ tự động khởi động lại trong vài giây để duy trì hiệu suất tối ưu.\n"
                        "⏰ Thời gian: Mỗi 12 tiếng một lần."
                    )
                    logger.info(f"✅ Đã gửi thông báo restart cho owner (ID: {owner_id})")
        except Exception as e:
            # Không cần báo lỗi nếu không gửi được thông báo
            logger.debug(f"Không thể gửi thông báo restart: {e}")


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
    
    # Vòng lặp restart tự động
    while True:
        # Start bot
        bot = BlastBot()
        
        try:
            await bot.start(token)
        except KeyboardInterrupt:
            logger.info("⚠️ Nhận tín hiệu KeyboardInterrupt (Ctrl+C)")
            if not bot.is_closed():
                await bot.close()
            break  # Thoát vòng lặp khi người dùng dừng thủ công
        except Exception as e:
            logger.error(f"❌ Lỗi khi chạy bot: {e}", exc_info=True)
        finally:
            if not bot.is_closed():
                await bot.close()
        
        # Kiểm tra xem có phải restart tự động không
        if bot.auto_restart_task and not bot.auto_restart_task.cancelled():
            logger.info("🔄 Đang khởi động lại bot...")
            await asyncio.sleep(5)  # Chờ 5 giây trước khi restart
        else:
            # Nếu không phải restart tự động thì thoát
            logger.info("🛑 Bot đã dừng hoàn toàn")
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("✅ Bot đã được tắt bởi người dùng")
    except Exception as e:
        logger.error(f"❌ Lỗi nghiêm trọng: {e}", exc_info=True)
