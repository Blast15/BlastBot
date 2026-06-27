# BlastBot 🚀

Discord bot hiện đại viết bằng `discord.py`, tập trung vào moderation và feedback, với slash commands là chính (vẫn hỗ trợ prefix commands).

## ✨ Tính năng

- **Slash commands** với autocomplete cho lý do moderation
- **Moderation**: kick, ban, softban, timeout, clear, temprole
- **Cảnh cáo**: warn và theo dõi số lần cảnh cáo (`/warnings`)
- **Quản lý role**: xem thông tin, thêm/xóa role
- **Context menus**: thao tác chuột phải trên user và message
- **Feedback**: modal góp ý với voting persistent (lưu qua restart)
- **Database**: SQLite bất đồng bộ (`aiosqlite`) ở chế độ WAL, có cache config
- **Error handling** tập trung với thông báo thân thiện
- **Logging** ra console và file UTF-8 (`bot.log`)

## 🏗️ Cấu trúc

```
BlastBot/
├── main.py              # Entry point, class BlastBot
├── cogs/                # Command groups (auto-discovery)
│   ├── core/            # Help
│   ├── interactions/    # Context menus
│   ├── moderation/      # kick, ban, softban, timeout, clear, warn, temprole
│   └── utilities/       # Role management, feedback
├── events/              # Event handlers (error handler cho prefix commands)
├── utils/               # database, embeds, views, modals, error_handler, config
├── tests/               # Unit tests
└── data/                # SQLite database (tạo tự động)
```

## 📦 Cài đặt

**Yêu cầu:** Python 3.12+ và một [Discord Bot Token](https://discord.com/developers/applications).

```bash
# 1. Clone
git clone <repository-url>
cd BlastBot

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Dependencies
pip install -r requirements.txt
# Dev tools (tùy chọn): pip install -e ".[dev]"

# 4. Cấu hình
cp .env.example .env             # rồi điền token vào .env

# 5. Chạy
python main.py
```

## ⚙️ Biến môi trường

| Biến | Bắt buộc | Mặc định | Mô tả |
|------|----------|----------|-------|
| `DISCORD_TOKEN` | ✅ | — | Bot token |
| `DB_PATH` | | `./data/bot.db` | Đường dẫn file SQLite |
| `GUILD_ID` | | — | Guild ID để sync command tức thì (dev) |
| `BOT_PREFIX` | | `!` | Prefix cho prefix commands |
| `OWNER_ID` | | — | User ID cho lệnh owner-only |

> Để trống `GUILD_ID` sẽ sync command global (có thể mất tới ~1 giờ để cập nhật).

## 🎮 Lệnh

**Moderation**
- `/kick <member> [reason]` — Kick member khỏi server
- `/ban <member> [reason] [delete_messages]` — Ban member
- `/softban <member> [reason] [delete_messages]` — Ban rồi unban ngay để xóa tin nhắn
- `/timeout <member> <duration> [reason]` — Timeout member
- `/clear <amount>` — Xóa hàng loạt tin nhắn
- `/temprole <member> <role> <duration> [reason]` — Gán role tạm thời, tự gỡ khi hết hạn
- `/warn <member> [reason]` — Cảnh cáo member
- `/warnings <member>` — Xem số cảnh cáo

**Role**
- `/roleinfo <role>` — Xem thông tin chi tiết role
- `/roleadd <member> <role>` — Thêm role cho member
- `/roleremove <member> <role>` — Xóa role khỏi member

**Khác**
- `/help [command]` — Danh sách lệnh hoặc chi tiết một lệnh
- `/suggest` — Gửi góp ý cho server

**Context menus** (chuột phải vào user/message): Thông tin User, Xem Avatar, Báo cáo User, Báo cáo Message, Bookmark Message.

## 🗃️ Database

SQLite bất đồng bộ qua `aiosqlite`, chạy ở chế độ **WAL** với một connection dùng chung (được tuần tự hóa bằng lock cho các thao tác ghi). Tables tự tạo ở lần chạy đầu.

Config của guild được cache với TTL 5 phút:

```python
bot.db.invalidate_cache(guild_id)   # xóa cache một guild
bot.db.invalidate_cache()           # xóa toàn bộ cache
bot.db.get_cache_stats()            # thống kê cache
```

## 🛠️ Phát triển

Lệnh được tổ chức thành cogs trong `cogs/` và **tự động được load** khi khởi động. Các moderation cog kế thừa `BaseModerationCog` để dùng chung logic validate quyền, hierarchy và logging.

**Thêm lệnh mới** — tạo file cog trong thư mục phù hợp:

```python
# cogs/utilities/example.py
import discord
from discord import app_commands
from discord.ext import commands

class Example(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="example")
    async def example(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")

async def setup(bot):
    await bot.add_cog(Example(bot))
```

Cog sẽ được load tự động ở lần khởi động sau.

**Chất lượng code** (cần `pip install -e ".[dev]"`):

```bash
ruff check --fix .    # lint + tự sửa
ruff format .         # format
pytest                # chạy test
```

> Mẹo: đặt `GUILD_ID` trong `.env` để sync command tức thì khi dev, thay vì chờ global sync (~1 giờ).

## 📝 Logging

Log ghi đồng thời ra **console** và file **`bot.log`** (UTF-8). Các mức: `INFO`, `WARNING`, `ERROR`, `DEBUG`.

> Log được tự động xoay vòng với `RotatingFileHandler` (tối đa 5MB x 5 file backup).

## 🐛 Khắc phục sự cố

**Lệnh không xuất hiện?** Kiểm tra `GUILD_ID`, chờ global sync (tới ~1 giờ), hoặc reload Discord (Ctrl+R).

**Lỗi database?** Đảm bảo thư mục `data/` tồn tại và ghi được; kiểm tra `DB_PATH`. Xóa `data/bot.db` để reset (sẽ mất dữ liệu).

**Bot không phản hồi?** Kiểm tra `DISCORD_TOKEN`, quyền của bot trong server, và xem `bot.log`.

## 🤝 Đóng góp

Fork → tạo feature branch → commit → mở pull request. Vui lòng chạy `ruff` và `pytest` trước khi gửi.

## 📄 License

Phát hành theo **GNU AGPL v3.0** — xem [LICENSE](LICENSE).

> AGPL-3.0 yêu cầu: nếu bạn chạy phiên bản đã chỉnh sửa như một network service, bạn phải cung cấp mã nguồn đầy đủ cho người dùng dịch vụ đó.

## 🔗 Liên kết

- [discord.py docs](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/applications)

---

Made with ❤️ using discord.py
