# BlastBot - Discord Bot

BlastBot là một bot Discord đa năng được phát triển bằng Python kết hợp với thư viện discord.py. Dự án này được tạo ra nhằm mục đích học tập và cung cấp các tính năng quản lý server cơ bản, tiện ích và giải trí cho người dùng Discord.

![BlastBot Logo](assets/blastbot_logo.png)

## Tính năng

### Quản lý Server
- **Kick**: Đá thành viên ra khỏi server
  - Hỗ trợ gửi thông báo lý do đá thành viên
  - Lưu lại log hoạt động
- **Ban**: Cấm thành viên khỏi server 
  - Cấm vĩnh viễn hoặc có thời hạn
  - Tùy chọn xóa tin nhắn của thành viên bị cấm
- **Timeout**: Tạm thời khóa quyền chat của thành viên
  - Hỗ trợ đặt thời gian timeout linh hoạt
  - Tự động hết hạn timeout sau khoảng thời gian quy định

### Tiện ích
- **Sync/Unsync**: Đồng bộ hóa lệnh slash cho toàn bot hoặc từng server
  - Hỗ trợ đồng bộ toàn cầu (global) hoặc theo server (guild)
  - Chỉ có chủ sở hữu bot mới có quyền sử dụng
- **Setp**: Tùy chỉnh prefix cho từng server
  - Lưu trữ cấu hình riêng biệt cho mỗi server
  - Tự động khôi phục cấu hình khi bot khởi động lại

### Giải trí
- **Random Pokemon**: Hiển thị thông tin ngẫu nhiên về Pokemon thế hệ 1
  - Hiển thị hình ảnh, thông số và thông tin chi tiết
  - Dữ liệu được cập nhật từ PokeAPI
  - Hỗ trợ tìm kiếm theo tên hoặc ID

## Kiến trúc hệ thống

BlastBot được xây dựng theo mô hình modular với cấu trúc thư mục sau:

```
BlastBot/
├── bot.py               # Điểm khởi chạy chính
├── cogs/                # Các module chức năng
│   ├── admin.py         # Lệnh quản trị
│   ├── moderation.py    # Lệnh điều hành
│   └── entertainment.py # Lệnh giải trí
├── utils/               # Tiện ích và helper
│   ├── db.py            # Xử lý cơ sở dữ liệu
│   └── logging.py       # Hệ thống ghi log
├── .env                 # Cấu hình môi trường
└── requirements.txt     # Các thư viện cần thiết
```

## Yêu cầu

### Yêu cầu hệ thống
- Python 3.8 trở lên
- Internet ổn định để kết nối tới Discord API
- Dung lượng đĩa tối thiểu: 100MB

### Thư viện cần thiết
- discord.py >= 2.0.0
- python-dotenv >= 0.19.0
- aiosqlite >= 0.17.0
- requests >= 2.27.0

## Cài đặt

### Cài đặt thông thường

1. Clone repository này về máy:
```bash
git clone https://github.com/username/BlastBot.git
cd BlastBot
```

2. Cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

3. Tạo file `.env` và thêm token bot Discord:
```
TOKEN=your_bot_token_here
OWNER_ID=your_discord_id_here
```

4. Khởi động bot:
```bash
python bot.py
```

### Cài đặt với Docker

1. Xây dựng Docker image:
```bash
docker build -t blastbot .
```

2. Chạy container:
```bash
docker run -d --name blastbot-container -e TOKEN=your_bot_token_here blastbot
```

## Sử dụng

Prefix mặc định của bot là `?`. Bạn có thể thay đổi prefix này cho server của mình bằng lệnh `setp`.

### Lệnh Admin
- `?sync [global|guild]` - Đồng bộ lệnh slash (chỉ owner)
  - `global`: Đồng bộ lệnh slash cho tất cả các server
  - `guild`: Đồng bộ lệnh slash chỉ cho server hiện tại
- `?unsync [global|guild]` - Hủy đồng bộ lệnh slash (chỉ owner)
  - `global`: Hủy đồng bộ lệnh slash cho tất cả các server
  - `guild`: Hủy đồng bộ lệnh slash chỉ cho server hiện tại
- `?setp <prefix>` - Đặt prefix mới cho server (cần quyền admin)
  - Ví dụ: `?setp !` sẽ đổi prefix từ `?` thành `!`

### Lệnh Mod
- `?kick <member> [reason]` - Đá thành viên (cần quyền kick)
  - `member`: Người dùng cần đá (mention hoặc ID)
  - `reason`: Lý do đá thành viên (tùy chọn)
- `?ban <member> [reason]` - Cấm thành viên (cần quyền ban)
  - `member`: Người dùng cần cấm (mention hoặc ID)
  - `reason`: Lý do cấm thành viên (tùy chọn)
- `?timeout <member> <duration> [reason]` - Khóa chat thành viên (cần quyền quản lý)
  - `member`: Người dùng cần timeout (mention hoặc ID)
  - `duration`: Thời gian timeout (1s, 1m, 1h, 1d)
  - `reason`: Lý do timeout thành viên (tùy chọn)

### Lệnh Giải trí  
- `?rd [name|id]` - Hiển thị thông tin Pokemon ngẫu nhiên (cooldown 5s)
  - Không tham số: Hiển thị Pokemon ngẫu nhiên
  - `name`: Tìm Pokemon theo tên
  - `id`: Tìm Pokemon theo ID

## Tùy chỉnh và mở rộng

### Thêm lệnh mới
Bạn có thể thêm lệnh mới bằng cách tạo file mới trong thư mục `cogs/`. Tham khảo các file cogs hiện có để biết cấu trúc:

```python
from discord.ext import commands

class NewFeature(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command()
    async def new_command(self, ctx):
        await ctx.send("Đây là lệnh mới!")
        
async def setup(bot):
    await bot.add_cog(NewFeature(bot))
```

### Cấu hình nâng cao
Bạn có thể chỉnh sửa cấu hình nâng cao của bot trong file `config.json`:

```json
{
  "cooldowns": {
    "entertainment": 5,
    "moderation": 3
  },
  "embed_color": "#3498db",
  "logging_level": "INFO"
}
```

## Đóng góp

Mọi đóng góp đều được chào đón! Để đóng góp vào dự án:

1. Fork repository
2. Tạo nhánh mới (`git checkout -b feature/amazing-feature`)
3. Commit thay đổi của bạn (`git commit -m 'Add amazing feature'`)
4. Push lên nhánh của bạn (`git push origin feature/amazing-feature`)
5. Mở Pull Request

### Hướng dẫn code style
- Tuân thủ PEP 8
- Sử dụng f-strings thay vì string concatenation
- Viết docstring cho tất cả các hàm và lớp

## Xử lý sự cố

### Vấn đề phổ biến

1. **Bot không online**
   - Kiểm tra token bot trong file `.env`
   - Kiểm tra internet connection
   - Kiểm tra log cho lỗi cụ thể

2. **Lệnh không hoạt động**
   - Đảm bảo bot có đủ quyền trong server
   - Kiểm tra prefix đang sử dụng
   - Thử sync lại lệnh với `?sync guild`

## Lưu ý

- Bot sử dụng SQLite để lưu cấu hình cho từng server
  - File database được lưu tại `data/server_config.db`
  - Backup tự động mỗi 24 giờ
- Có logging đầy đủ cho việc debug
  - Log được lưu tại `logs/bot.log`
  - Xoay vòng log mỗi 7 ngày
- Prefix mặc định là `?` nếu chưa được cấu hình
- Cần cấp quyền đầy đủ cho bot khi thêm vào server

## Giấy phép

Dự án này được phân phối dưới giấy phép MIT. Xem file `LICENSE` để biết thêm chi tiết.

## Liên hệ

Nếu bạn có bất kỳ câu hỏi nào, vui lòng liên hệ:
- Discord: blastsama
- Email: nguyenhuutrungchien15@gmail.com
- GitHub Issues: [Tạo issue mới](https://github.com/username/BlastBot/issues)