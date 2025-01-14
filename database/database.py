import sqlite3
from pathlib import Path

class Database:
    """Lớp xử lý kết nối và thao tác với cơ sở dữ liệu SQLite"""
    
    def __init__(self):
        # Tạo thư mục database nếu chưa tồn tại
        db_dir = Path('./database')
        db_dir.mkdir(exist_ok=True)
        
        # Kết nối đến cơ sở dữ liệu SQLite (tạo mới nếu chưa tồn tại)
        self.conn = sqlite3.connect('./database/bot.db')
        self.cursor = self.conn.cursor()
        self.setup()

    def setup(self):
        """Khởi tạo các bảng trong cơ sở dữ liệu"""
        # Tạo bảng guilds để lưu cấu hình cho mỗi server
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,      -- ID của server Discord
            prefix TEXT DEFAULT '$',           -- Prefix tùy chỉnh cho server
            log_channel INTEGER,               -- Kênh log
            welcome_channel INTEGER,           -- Kênh chào mừng
            mod_role INTEGER,                  -- Role người kiểm duyệt
            admin_role INTEGER,                -- Role quản trị viên
            auto_role INTEGER,                 -- Role tự động gán
            welcome_message TEXT               -- Tin nhắn chào mừng
            )
        ''')

        # Tạo bảng temprole để lưu role tạm thời
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS temprole (
            guild_id INTEGER,                          -- ID của server Discord
            user_id INTEGER,                           -- ID của người dùng
            role_id INTEGER,                           -- ID của role
            time INTEGER,                              -- Thời gian còn lại
            PRIMARY KEY (guild_id, user_id, role_id)
            )
        ''')
        self.conn.commit()
    
    def close(self):
        """Đóng kết nối database"""
        self.conn.close()

    def __del__(self):
        """Hàm hủy để đảm bảo đóng kết nối"""
        self.close()