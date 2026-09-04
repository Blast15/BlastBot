# BlastBot

BlastBot là Discord bot đa năng viết bằng Python, tập trung vào moderation, role, automation và theo dõi Reddit. Dự án dùng slash command, SQLite bất đồng bộ và cấu hình hoàn toàn qua biến môi trường.

**Phiên bản hiện tại:** `4.0.2`

## Tính năng

- Moderation: kick, ban, softban, timeout, clear, warn và temporary role.
- Report User / Report Message qua context menu, gửi về moderation log channel.
- Role management và persistent self-assign role menu.
- Welcome, goodbye và auto-message định kỳ.
- Reddit subscription theo server, hỗ trợ OAuth hoặc RSS công khai, lọc bài có ảnh.
- Help động, cấu hình log channel và structured logging tùy chọn.

## Cài đặt

Yêu cầu Python 3.11 trở lên.

```bash
git clone https://github.com/Blast15/BlastBot.git
cd BlastBot
python -m venv .venv
```

Kích hoạt môi trường (`.venv\\Scripts\\activate` trên Windows hoặc `source .venv/bin/activate` trên Linux/macOS), sau đó:

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Trên Windows, dùng `Copy-Item .env.example .env` thay cho `cp`.

## Cấu hình

`DISCORD_TOKEN` là biến bắt buộc. Các biến còn lại có giá trị mặc định trong `.env.example`.

| Biến | Mô tả |
| --- | --- |
| `DISCORD_TOKEN` | Bot token từ Discord Developer Portal |
| `OWNER_ID` | Discord user ID của owner, có thể để trống |
| `DEV_GUILD_ID` | Server dùng khi `SYNC_MODE=dev_guild` |
| `DATABASE_URL` | SQLAlchemy async URL, mặc định SQLite trong `data/` |
| `LOG_LEVEL`, `LOG_JSON` | Mức log và định dạng JSON |
| `SYNC_MODE` | `none`, `dev_guild` hoặc `global` |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | OAuth application credentials, có thể để trống khi dùng RSS |
| `REDDIT_USER_AGENT` | Chuỗi định danh client Reddit |
| `REDDIT_POLL_INTERVAL` | Chu kỳ poll, từ 60 đến 3600 giây |
| `REDDIT_KEYLESS_FALLBACK` | Cho phép RSS khi không có OAuth |
| `FEATURE_*` | Bật/tắt từng module còn được hỗ trợ |

Không commit file `.env` hoặc token. Với Reddit OAuth, tạo application loại `script` và đặt user-agent riêng, rõ ràng.

## Discord

Bật **Server Members Intent** trong Developer Portal. Message Content Intent không cần thiết.

Khi invite bot, chọn scope `bot` và `applications.commands`. Quyền tối thiểu phụ thuộc tính năng sử dụng: View Channels, Send Messages, Embed Links, Manage Roles, Moderate Members, Kick Members, Ban Members và Manage Messages. Role của bot phải nằm trên role/member mà bot quản lý.

Command không tự sync mặc định. Dùng `SYNC_MODE=dev_guild` khi phát triển; chỉ dùng `global` khi cần publish command toàn cục, sau đó có thể trả về `none`.

## Command chính

- `/help [command]`
- `/config logchannel`, `/config view`
- `/kick`, `/ban`, `/softban`, `/timeout`, `/clear`, `/warn`, `/warnings`, `/temprole`
- `/roleadd`, `/roleremove`, `/rolemenu create|list|delete`
- `/greeting welcome|goodbye|disable|test`
- `/automsg add|list|delete|toggle`
- `/reddit add|list|remove|toggle|test`

Context menu trong **Apps** cung cấp thông tin user, avatar, bookmark và report user/message.

## Cấu trúc

```text
blastbot/
├── core/          # Bot, settings, error handling, logging
├── database/      # SQLAlchemy engine và models
├── modules/       # Feature cogs, validation/service và persistence
└── shared/        # UI, embed, permission và validation dùng chung
tests/             # Smoke và regression tests
main.py            # Entrypoint
```

Service được giữ ở nơi có validation hoặc quy tắc nghiệp vụ; repository chịu trách nhiệm transaction và query. SQLite bật WAL, foreign keys và busy timeout khi kết nối.

## Độ tin cậy khi vận hành

Reddit và auto-message dùng delivery **at-least-once**: bot gửi Discord trước rồi mới lưu
cursor. Nếu gửi thành công nhưng SQLite lỗi, lần poll sau có thể gửi trùng bài/tin vừa gửi;
thứ tự này chủ ý ưu tiên duplicate có thể nhận biết thay vì mất message âm thầm. Cursor Reddit
được lưu theo từng subscription và cập nhật sau từng bài đã gửi hoặc đã bỏ qua bởi `images_only`.

OAuth Reddit catch up riêng từng subreddit, tối đa 3 trang × 100 bài mỗi poll và gửi theo thứ tự
cũ đến mới. Nếu cursor cũ nằm ngoài cửa sổ đó, bot ghi warning và bỏ phần backlog cũ hơn cửa
sổ thay vì âm thầm bỏ qua. RSS công khai không cung cấp pagination tương đương; ceiling là một
feed tối đa 100 bài và bot áp dụng cùng warning/policy khi không còn thấy cursor.

Schema được nâng tự động bằng các migration có version, chạy theo thứ tự và idempotent khi bot
khởi động. Deployment SQLite hỗ trợ một process bot ghi vào mỗi database. Cần persist `data/`;
`logs/` nên được giữ hoặc chuyển sang log collector. Để backup nhất quán, dừng bot rồi sao chép
file database (hoặc dùng lệnh `.backup` của SQLite); để restore, dừng bot, thay file trong `data/`,
rồi khởi động lại để migration còn thiếu tự chạy.

## Development

```bash
ruff check .
pytest -q
python -m compileall -q blastbot main.py
python -c "import blastbot"
```

Production nên chạy bot dưới process supervisor hoặc container có restart policy, mount bền vững
thư mục `data/` và `logs/`, và gửi `SIGTERM` khi deploy để Discord/HTTP/database đóng sạch. Dùng
Python 3.11 trở lên. Nên sync command ở môi trường dev trước; chỉ bật `SYNC_MODE=global` cho lần
publish cần thiết rồi trả về `none` để tránh sync không chủ ý mỗi lần restart.

## License

Phát hành theo [MIT License](LICENSE).
