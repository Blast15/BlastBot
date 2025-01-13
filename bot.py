import discord
from discord.ext import commands
from database.database import Database
from dotenv import load_dotenv
import os
import sys

# Tải các biến môi trường
try:
    load_dotenv()
    TOKEN = os.getenv('TOKEN')
    if not TOKEN:
        raise ValueError("Không tìm thấy Token trong tệp .env")
except Exception as e:
    print(f"Lỗi khi tải biến môi trường: {e}")
    sys.exit(1)

class Bot(commands.Bot):
    """
    Lớp chính của Bot Discord
    Xử lý việc khởi tạo, kết nối và quản lý các tính năng cơ bản của bot
    """
    def __init__(self):
        # Khởi tạo các quyền cần thiết cho bot
        intent = discord.Intents.default()
        intent.message_content = True  # Cho phép bot đọc nội dung tin nhắn
        super().__init__(
            command_prefix=self.get_prefix,  # Sử dụng prefix động
            intents=intent,
            description="Đố ông biết đấy!!",  # Mô tả bot
            help_command=None  # Tắt lệnh trợ giúp mặc định
        )
        # Khởi tạo kết nối database
        self.db = Database()

    async def on_ready(self):
        # In thông tin khi bot đã sẵn sàng hoạt động
        print(f'Đã đăng nhập với tên {self.user} (ID: {self.user.id})')
        print(f'Đã kết nối với {len(self.guilds)} máy chủ')
        print('------')
        
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
                    print(f"Lỗi khi dỡ extension {extension}: {e}")

            # Tải các lệnh từ thư mục commands
            if not os.path.exists('./commands'):
                print("Không tìm thấy thư mục commands")
                return

            for filename in os.listdir('./commands'):
                if filename.endswith(".py"):
                    extension = filename[:-3]
                    try:
                        await bot.load_extension(f"commands.{extension}")
                        print(f"Đã tải extension '{extension}'")
                    except Exception as e:
                        print(f"Lỗi khi tải extension {extension}: {e}")
             
            # Tải các sự kiện từ thư mục events
            if not os.path.exists('./events'):
                print("Không tìm thấy thư mục events")
                return
            
            for filename in os.listdir('./events'):
                if filename.endswith(".py"):
                    extension = filename[:-3]
                    try:
                        await bot.load_extension(f"events.{extension}")
                        print(f"Đã tải extension '{extension}'")
                    except Exception as e:
                        print(f"Lỗi khi tải extension {extension}: {e}")

        except Exception as e:
            print(f"Lỗi trong setup_hook: {e}")

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
        else:
            raise exception

# Khởi động bot
try:
    bot = Bot()
    bot.run(TOKEN)
except discord.LoginFailure:
    print("Đăng nhập thất bại: Token không hợp lệ")
    sys.exit(1)
except Exception as e:
    print(f"Lỗi khi chạy bot: {e}")
    sys.exit(1)