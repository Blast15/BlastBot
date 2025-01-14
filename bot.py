import discord
from discord.ext import commands
from database.database import Database
from dotenv import load_dotenv
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from utils.config import Config

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
    """A custom logging formatter that adds colors and styling to log messages.
    This formatter adds ANSI color codes and text styling to different parts of the log message,
    making it easier to distinguish between different log levels and components in the output.
    Attributes:
        black (str): ANSI code for black text
        red (str): ANSI code for red text
        green (str): ANSI code for green text
        yellow (str): ANSI code for yellow text
        blue (str): ANSI code for blue text
        gray (str): ANSI code for gray text
        reset (str): ANSI code to reset all formatting
        bold (str): ANSI code for bold text
        COLORS (dict): Mapping of logging levels to their corresponding color codes
    Format:
        The log format is: timestamp levelname name message
        - timestamp: Bold black
        - levelname: Color based on log level (padded to 8 characters)
        - name: Bold green
        - message: Default color
    Note:
        This formatter assumes the terminal supports ANSI color codes.
    """
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
        """
        Format a log record with colored output.

        This method formats logging records with ANSI color codes for enhanced readability.
        Colors are applied to the timestamp (black), log level (varies by level), and logger name (green).

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted log message with ANSI color codes.

        Format structure:
            "{timestamp} {level} {logger_name} {message}"
            - timestamp: Black, bold
            - level: Color based on level severity, 8 characters left-aligned
            - logger_name: Green, bold
            - message: Default color

        Example output:
            2023-05-20 14:30:45 INFO     Logger  Sample log message
        """
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)

intents = discord.Intents.default()
intents.message_content = True  # Cho phép bot đọc nội dung tin nhắn
intents.members = True  # Cho phép bot đọc thông tin thành viên

class Bot(commands.Bot):
    """A custom Discord bot class extending discord.ext.commands.Bot.
    This bot implements custom prefix handling, logging, and automatic extension loading.
    Attributes:
        logger (logging.Logger): The bot's logger instance for tracking events and errors
        db (Database): Database connection instance for storing bot configurations
    Methods:
        setup_logger(): Configures logging with both console and file output
        on_ready(): Callback when bot is ready and connected to Discord
        setup_hook(): Loads command and event extensions from respective directories
        get_prefix(message): Retrieves custom prefix for each guild or default prefix
        on_command_error(ctx, exception): Handles various command execution errors
    Example:
        bot = Bot()
        bot.run(token)
    """
    def __init__(self):
        # Khởi tạo các quyền cần thiết cho bot
        super().__init__(
            command_prefix=self.get_prefix,  # Sử dụng prefix động
            intents=intents,
            description="Đố ông biết đấy!!",  # Mô tả bot
            help_command=None  # Tắt lệnh trợ giúp mặc định
        )
        self.setup_logger()
        # Khởi tạo kết nối database
        self.db = Database()
    
    def setup_logger(self):
        """
        Sets up logging configuration for the bot.
        This method initializes a logger with both console and file handlers:
        - Console handler: Uses custom LoggingFormatter for colored output
        - File handler: Creates rotating log files with the following parameters:
            - Filename: discord.log
            - Max file size: 10MB
            - Backup count: 5 files
            - UTF-8 encoding
            - Format: [timestamp] [level] name: message
        The logger is set to INFO level and stores logs in both console and file outputs.
        Returns:
            None
        """
        self.logger = logging.getLogger("blast_bot")
        self.logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(LoggingFormatter())
        # File handler
        file_handler = RotatingFileHandler(
            filename="discord.log",
            maxBytes=10000000,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler_formatter = logging.Formatter(
            "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
        )
        file_handler.setFormatter(file_handler_formatter)

        # Thêm các handler
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)


    async def on_ready(self):
        """
        A coroutine that runs when the bot is ready and connected to Discord.
        This event handler executes once when the bot successfully connects to Discord.
        It performs the following tasks:
        - Logs the bot's username and ID
        - Logs the number of connected servers (guilds)
        - Sets the bot's presence status with custom activity showing server count
        Returns:
            None
        """
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
        """
        Asynchronous setup hook method for initializing bot extensions.
        This method performs the following setup tasks:
        1. Unloads all currently loaded extensions
        2. Loads command extensions from the 'commands' directory
        3. Loads event extensions from the 'events' directory
        The method handles extensions with .py files only and logs the status 
        of loading/unloading operations.
        Returns:
            None
        Raises:
            Exception: If there are errors during setup process, they are logged 
                      but not propagated
        """
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
        """
        Gets the command prefix for the bot based on the message context.
        This method retrieves the custom prefix for a guild from the database if one exists,
        otherwise returns the default prefix. For direct messages, it always returns the default prefix.
        Parameters
        ----------
        message : discord.Message
            The message object to get the prefix for
        Returns
        -------
        str
            The command prefix to use - either the custom prefix for the guild or the default prefix
        Examples
        --------
        If message is from a guild with custom prefix '$':
            >>> await bot.get_prefix(message)
            '$'
        If message is from DM or guild has no custom prefix:
            >>> await bot.get_prefix(message) 
            Config.DEFAULT_PREFIX
        """
        # Prefix mặc định của bot
        default_prefix = Config.DEFAULT_PREFIX

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

# Khởi động bot
try:
    bot = Bot()
    bot.run(Config.TOKEN)
except discord.LoginFailure:
    bot.logger.error("Đăng nhập thất bại: Token không hợp lệ")
    sys.exit(1)
except Exception as e:
    bot.logger.error(f"Lỗi khi chạy bot: {e}")
    sys.exit(1)