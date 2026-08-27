# BlastBot

BlastBot là Discord bot đa chức năng được viết bằng Python, tập trung vào kiến trúc module rõ ràng, dễ vận hành và dễ mở rộng.

Repository này là bản source tối giản dành cho việc chạy bot trực tiếp. Database SQLite được khởi tạo tự động khi bot khởi động, không cần chạy migration thủ công.

## Tính năng chính

- Moderation và warning system.
- Ticket system với panel, staff, blacklist, transcript, claim và autoclose.
- Role management và role menu.
- Feedback / suggestion system.
- Automation và greeting configuration.
- Context menu interactions.
- Slash-command help system.
- Guild-specific configuration.
- Feature flags cho từng module.

## Yêu cầu

- Python 3.13 được khuyến nghị.
- Discord Bot Token.

## Cài đặt

Clone repository:

```bash
git clone https://github.com/Blast15/BlastBot.git
cd BlastBot
```

Tạo virtual environment:

### Windows

```powershell
py -3.13 -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

Cài dependency:

```bash
pip install -r requirements.txt
```

## Cấu hình

Sao chép `.env.example` thành `.env`:

### Windows

```powershell
copy .env.example .env
```

### Linux / macOS

```bash
cp .env.example .env
```

Sau đó chỉnh các giá trị cần thiết:

```env
DISCORD_TOKEN=your_bot_token
BOT_PREFIX=!
OWNER_ID=
DEV_GUILD_ID=
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
LOG_LEVEL=INFO
LOG_JSON=false
SYNC_MODE=none
TRANSCRIPT_MESSAGE_LIMIT=2000
FEATURE_MODERATION=true
FEATURE_TICKETS=true
FEATURE_AUTOMATION=true
FEATURE_FEEDBACK=true
FEATURE_ROLES=true
FEATURE_CONTEXT_MENUS=true
```

### Command sync

`SYNC_MODE` hỗ trợ:

- `none`: không tự sync command khi startup.
- `dev_guild`: sync vào guild được khai báo bằng `DEV_GUILD_ID`, phù hợp khi phát triển.
- `global`: sync global command tree.

Trong quá trình phát triển nên dùng `dev_guild` để command cập nhật nhanh hơn.

## Chạy bot

```bash
python main.py
```

Hoặc:

```bash
python -m blastbot
```

Khi dùng cấu hình SQLite mặc định, database sẽ được tạo tại:

```text
data/bot.db
```

Các bảng cần thiết được kiểm tra và tạo tự động khi bot khởi động.

## Cấu trúc source

```text
BlastBot/
├── blastbot/
│   ├── core/           # bot lifecycle, config, error handling, context
│   ├── database/       # SQLAlchemy models và database session
│   ├── modules/        # các feature của bot
│   └── shared/         # thành phần dùng chung nhỏ
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── .gitattributes
├── LICENSE
└── README.md
```

Các feature lớn nằm trong `blastbot/modules/` và được tách theo domain thay vì gom toàn bộ logic vào một file bot duy nhất.

## Discord Developer Portal

Tạo application/bot tại Discord Developer Portal, lấy Bot Token và đặt vào `DISCORD_TOKEN` trong `.env`.

Chỉ bật các privileged intents thực sự cần cho những feature bạn sử dụng. Nếu thay đổi intent hoặc quyền của bot, cần cập nhật tương ứng trong Discord Developer Portal và quyền role của bot trong server.

## Database

Mặc định BlastBot dùng SQLite thông qua `aiosqlite`:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
```

Không commit thư mục `data/`, file `.db` hoặc `.env` lên GitHub.

## Cập nhật source trên server

```bash
git pull origin main
pip install -r requirements.txt
python main.py
```

Nếu chạy bot bằng process manager như systemd, PM2 hoặc Docker bên ngoài repository này, restart process sau khi pull.

## Bảo mật

- Không commit `.env` hoặc Discord token.
- Không hard-code token/API key vào source.
- Nếu token từng bị public, reset token ngay trong Discord Developer Portal.
- Chỉ cấp cho bot các Discord permissions thực sự cần thiết.

## License

Dự án được phát hành theo giấy phép [MIT](LICENSE).
