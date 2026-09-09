# BlastBot

BlastBot là Discord bot đa năng viết bằng Python, tập trung vào moderation, role, automation và theo dõi Reddit. Dự án dùng slash command, SQLite bất đồng bộ và cấu hình hoàn toàn qua biến môi trường.

**Phiên bản hiện tại:** `4.2.0`

## Tính năng

- Moderation: kick, ban, softban, timeout, clear, warn và temporary role.
- Report User / Report Message qua context menu, gửi về moderation log channel.
- Role management và persistent self-assign role menu.
- Welcome, goodbye và auto-message định kỳ.
- Reddit subscription theo server, hỗ trợ OAuth hoặc RSS công khai, lọc bài có ảnh.
- Help tương tác: menu nhóm/lệnh, phân trang, tìm theo mô tả, tham số và quyền mặc định.
- Tiện ích: ping, botinfo, serverinfo, userinfo và avatar.
- Bình chọn Discord gốc và slowmode kênh có audit log trong database.
- AutoMod native kiểu Dyno: chống spam, mention spam/raid và chặn link invite Discord.
- Cấu hình log channel và structured logging tùy chọn.

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

Khi invite bot, chọn scope `bot` và `applications.commands`. Quyền tối thiểu phụ thuộc tính năng sử dụng: View Channels, Send Messages, Embed Links, Manage Server, Manage Roles, Moderate Members, Kick Members, Ban Members và Manage Messages. Role của bot phải nằm trên role/member mà bot quản lý.

Command không tự sync mặc định. Dùng `SYNC_MODE=dev_guild` khi phát triển; chỉ dùng `global` khi cần publish command toàn cục, sau đó có thể trả về `none`.

## Command chính

- `/help [command]` (tên lệnh hoặc từ khóa)
- `/ping`, `/botinfo`, `/serverinfo`, `/userinfo [member]`, `/avatar [member]`
- `/poll question options [hours] [multiple]`
- `/slowmode seconds`
- `/config logchannel`, `/config view`
- `/automod setup [mention_limit]`, `/automod status`, `/automod disable`
- `/kick`, `/ban`, `/softban`, `/timeout`, `/clear`, `/warn`, `/warnings`, `/temprole`
- `/roleadd`, `/roleremove`, `/rolemenu create|list|delete`
- `/greeting welcome|goodbye|disable|test`
- `/automsg add|list|delete|toggle`
- `/reddit add|list|remove|toggle|test`

Context menu trong **Apps** cung cấp thông tin user, avatar, bookmark và report user/message.

## Help và tiện ích cộng đồng

`/help` chỉ bạn nhìn thấy. Chọn nhóm rồi chọn lệnh để xem cú pháp, tham số, giá trị mặc định,
phạm vi số và quyền mặc định. Mỗi trang có tối đa 8 lệnh; nút Trang chủ, Danh sách, Trước/Sau
giúp quay lại nhanh. Menu hết hạn sau 3 phút không tương tác; dùng `/help` để mở lại.
`/help command:bình chọn` tìm theo mô tả; `/help command:reddit add` mở chi tiết lệnh.
Lệnh và context menu được lấy từ các module đang bật. Help không thay thế kiểm tra quyền lúc chạy.

| Lệnh | Ví dụ / hành vi | Quyền người dùng |
| --- | --- | --- |
| `/ping` | Độ trễ Gateway Discord, không phải benchmark database | Mọi thành viên |
| `/botinfo` | Version, thời gian hoạt động, số server/module | Mọi thành viên |
| `/serverinfo` | Chủ server, ngày tạo, số thành viên/kênh/role/boost | Mọi thành viên trong server |
| `/userinfo`, `/avatar` | Chọn member hoặc để trống để xem chính mình | Mọi thành viên trong server |
| `/poll` | `question:Đi chơi ngày nào? options:Thứ bảy \| Chủ nhật hours:24 multiple:false` | Manage Messages của server |
| `/slowmode` | `seconds:10`; `seconds:0` để tắt, tối đa 21600 giây | Manage Channels tại kênh |

Poll có 2–10 lựa chọn khác nhau, mỗi lựa chọn tối đa 55 ký tự; câu hỏi tối đa 300 ký tự,
thời lượng 1–168 giờ. Bình chọn hiển thị công khai trong kênh văn bản đang dùng lệnh,
Discord quản lý phiếu bầu và thời điểm kết thúc nên không phụ thuộc process bot.
Bot cần Send Messages và Send Polls tại kênh. Cooldown: một poll mỗi 30 giây/người/server.

Slowmode áp dụng cho kênh văn bản hiện tại, bot cũng cần Manage Channels. Cooldown 10 giây/kênh.
Thao tác ghi Discord audit reason và moderation log trong database; nếu lưu database lỗi sau khi
Discord đã đổi slowmode, bot báo rõ kết quả một phần. Lệnh chỉ điều chỉnh slowmode gốc của Discord.

AutoMod dùng rule native của Discord nên vẫn hoạt động khi process BlastBot dừng và không cần
Message Content Intent. `/automod setup` tạo hoặc cập nhật ba rule do BlastBot quản lý: anti-spam,
mention spam/raid (mặc định tối đa 5 mention mỗi message) và chặn link `discord.gg`/
`discord.com/invite`. Nếu đã cấu hình `/config logchannel`, rule cũng gửi alert vào kênh đó.
`/automod disable` chỉ tắt các rule mang tên BlastBot, không đụng vào AutoMod rule khác của server.

`FEATURE_UTILITY=false` tắt ping/botinfo/serverinfo/poll. Userinfo/avatar dùng chung phần xử lý
với context menu và đi theo `FEATURE_CONTEXT_MENUS`; slowmode đi theo `FEATURE_MODERATION`.
Sau nâng cấp, sync command ở dev guild trước như hướng dẫn Discord bên trên.

### Tham khảo thiết kế

- Dyno: danh mục lệnh utility, serverinfo, poll và help — https://docs.dyno.gg/commands
- Dyno: slowmode — https://docs.dyno.gg/modules/slowmode
- MEE6: Welcome — https://help.mee6.xyz/support/solutions/101000251022
- MEE6: Social Connectors — https://help.mee6.xyz/support/solutions/101000251024
- MEE6: Polls — https://help.mee6.xyz/support/solutions/articles/101000490535-how-to-disable-polls-plugin-and-commands

AutoMod mới dùng rule native của Discord thay vì tự đọc message; cách này giữ bot không cần
Message Content Intent và tránh thêm storage/worker chống spam riêng. XP/level, ticket và nhạc
chưa triển khai vì cần storage, chống lạm dụng hoặc hạ tầng riêng; Welcome/role menu/Reddit đã có
nên tiếp tục dùng module hiện tại.

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
