# BlastBot - Discord Bot

Bot Discord đơn giản được viết bằng Python và discord.py, phục vụ mục đích học tập.

## Tính năng

### Quản lý Server
- Kick: Đá thành viên ra khỏi server
- Ban: Cấm thành viên khỏi server 
- Timeout: Tạm thời khóa quyền chat của thành viên

### Tiện ích
- Sync/Unsync: Đồng bộ hóa lệnh slash cho toàn bot hoặc từng server
- Setp: Tùy chỉnh prefix cho từng server

### Giải trí
- Random Pokemon: Hiển thị thông tin ngẫu nhiên về Pokemon thế hệ 1

## Yêu cầu

- Python 3.8 trở lên

## Cài đặt

1. Clone repository này về máy:
```bash
git clone <repository-url>
```

2. Cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt
```

3. Tạo file `.env` và thêm token bot Discord:
```
TOKEN=<your_bot_token>
```

4. Khởi động bot:
```bash
python bot.py
```

## Sử dụng

### Lệnh Admin
- `sync [global|guild]` - Đồng bộ lệnh slash (chỉ owner)
- `unsync [global|guild]` - Hủy đồng bộ lệnh slash (chỉ owner)
- `setp <prefix>` - Đặt prefix mới cho server (cần quyền admin)

### Lệnh Mod
- `kick <member> [reason]` - Đá thành viên (cần quyền kick)
- `ban <member> [reason]` - Cấm thành viên (cần quyền ban)
- `timeout <member> <duration> [reason]` - Khóa chat thành viên (cần quyền quản lý)

### Lệnh Giải trí  
- `rd` - Hiển thị thông tin Pokemon ngẫu nhiên (cooldown 5s)

## Đóng góp

Mọi đóng góp đều được chào đơn. Vui lòng tạo issue hoặc pull request.

## Lưu ý

- Bot sử dụng SQLite để lưu cấu hình cho từng server
- Có logging đầy đủ cho việc debug
- Prefix mặc định là `?` nếu chưa được cấu hình