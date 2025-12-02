# BlastBot

Bot Discord hiện đại với slash commands và moderation tools.

## Tính năng

- Slash Commands đầy đủ
- Quản lý moderation (kick, ban, timeout, clear)
- Quản lý roles với menu tương tác
- Context menus (right-click)
- Database SQLite với caching

## Cài đặt

1. **Cài đặt dependencies:**
```bash
pip install -r requirements.txt
```

2. **Tạo file `.env`:**
```env
DISCORD_TOKEN=your_bot_token_here
DB_PATH=./data/bot.db
```

3. **Chạy bot:**
```bash
python main.py
```

## Commands

### Moderation
- `/kick` - Kick member
- `/ban` - Ban member
- `/timeout` - Timeout member
- `/clear` - Xóa messages

### Roles
- `/rolemenu` - Tạo role selection menu
- `/roleinfo` - Xem thông tin role
- `/roleadd` - Thêm role
- `/roleremove` - Xóa role

### Core
- `/help` - Hiển thị commands

## Yêu cầu

- Python 3.10+
- Discord Bot Token
