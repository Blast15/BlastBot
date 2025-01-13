import discord
from discord.ext import commands
from database.database import Database
from dotenv import load_dotenv
import os
import sys
import logging

# Tải các biến môi trường
try:
    load_dotenv()
    TOKEN = os.getenv('TOKEN')
    if not TOKEN:
        raise ValueError("Không tìm thấy Token trong tệp .env")
except Exception as e:
    print(f"Lỗi khi tải biến môi trường: {e}")
    sys.exit(1)


class LoggingFormatter(logging.Formatter):
    # Màu sắc
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # Kiểu chữ
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)
    

logger = logging.getLogger("blast_bot")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(LoggingFormatter())
# File handler
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler_formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
file_handler.setFormatter(file_handler_formatter)

# Thêm các handler
logger.addHandler(console_handler)
logger.addHandler(file_handler)

intents = discord.Intents.default()
intents.message_content = True  # Cho phép bot đọc nội dung tin nhắn

class Bot(commands.Bot):
    """
    Lớp chính của Bot Discord
    Xử lý việc khởi tạo, kết nối và quản lý các tính năng cơ bản của bot
    """
    def __init__(self):
        # Khởi tạo các quyền cần thiết cho bot
        super().__init__(
            command_prefix=self.get_prefix,  # Sử dụng prefix động
            intents=intents,
            description="Đố ông biết đấy!!",  # Mô tả bot
            help_command=None  # Tắt lệnh trợ giúp mặc định
        )
        self.logger = logger
        # Khởi tạo kết nối database
        self.db = Database()

    async def on_ready(self):
        # In thông tin khi bot đã sẵn sàng hoạt động
        self.logger.info(f"Đã đăng nhập với tên {self.user} (ID: {self.user.id})")
        self.logger.info(f"Đã kết nối với {len(self.guilds)} máy chủ")
        
        # Cài đặt trạng thái của bot
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.custom, 
                name=f'Đang phục vụ {len(self.guilds)} máy chủ'
            ),
            status=discord.Status.online
        )

    async def setup_hook(self):
        try:
            # Dỡ toàn bộ extension hiện có
            for extension in list(bot.extensions):
                try:
                    await bot.unload_extension(extension)
                except Exception as e:
                    self.logger.error(f"Lỗi khi dỡ extension {extension}: {e}")

            # Tải các lệnh từ thư mục commands
            if not os.path.exists('./commands'):
                self.logger.error("Không tìm thấy thư mục commands")
                return

            for filename in os.listdir('./commands'):
                if filename.endswith(".py"):
                    extension = filename[:-3]
                    try:
                        await bot.load_extension(f"commands.{extension}")
                        self.logger.info(f"Đã tải extension '{extension}'")
                    except Exception as e:
                        self.logger.error(f"Lỗi khi tải extension {extension}: {e}")
             
            # Tải các sự kiện từ thư mục events
            if not os.path.exists('./events'):
                self.logger.error("Không tìm thấy thư mục events")
                return
            
            for filename in os.listdir('./events'):
                if filename.endswith(".py"):
                    extension = filename[:-3]
                    try:
                        await bot.load_extension(f"events.{extension}")
                        self.logger.info(f"Đã tải extension '{extension}'")
                    except Exception as e:
                        self.logger.error(f"Lỗi khi tải extension {extension}: {e}")

        except Exception as e:
            self.logger.error(f"Lỗi trong setup_hook: {e}")

    async def get_prefix(self, message):
        # Prefix mặc định của bot
        default_prefix = '?'

        # Nếu tin nhắn không từ server nào, dùng prefix mặc định
        if message.guild is None:
            return default_prefix
        
        # Lấy prefix tùy chỉnh từ database
        try:
            self.db.cursor.execute(
                "SELECT prefix FROM guilds WHERE guild_id = ?",
                (message.guild.id,)
            )
            prefix = self.db.cursor.fetchone()
            return prefix[0] if prefix else default_prefix
        except Exception as e:
            return default_prefix
    
    async def on_command_error(self, ctx, exception):
        if isinstance(exception, commands.CommandNotFound):
            await ctx.send("Lệnh không tồn tại!")
        elif isinstance(exception, commands.MissingRequiredArgument):
            await ctx.send("Thiếu tham số cần thiết!")
        elif isinstance(exception, commands.MissingPermissions):
            await ctx.send("Bạn không có quyền thực hiện lệnh này!")
        elif isinstance(exception, commands.BotMissingPermissions):
            await ctx.send("Bot không có quyền thực hiện lệnh này!")
        elif isinstance(exception, commands.NotOwner):
            await ctx.send("Bạn không phải là chủ sở hữu của bot!")
        else:
            raise exception

# Khởi động bot
try:
    bot = Bot()
    bot.run(TOKEN)
except discord.LoginFailure:
    logger.error("Đăng nhập thất bại: Token không hợp lệ")
    sys.exit(1)
except Exception as e:
    logger.error(f"Lỗi khi chạy bot: {e}")
    sys.exit(1)