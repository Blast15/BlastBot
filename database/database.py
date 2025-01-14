import sqlite3
from pathlib import Path
import logging

class Database:
    """Xử lý kết nối và thao tác với SQLite database"""
    
    def __init__(self):
        self.logger = logging.getLogger('blast_bot')
        
        # Tạo thư mục database nếu chưa có
        db_dir = Path('./database')
        db_dir.mkdir(exist_ok=True)
        
        # Kết nối SQLite
        try:
            self.conn = sqlite3.connect('./database/bot.db')
            self.cursor = self.conn.cursor()
            self.setup()
            self.logger.info("Đã kết nối thành công với database")
        except Exception as e:
            self.logger.error(f"Lỗi kết nối database: {e}")
            raise

    def setup(self):
        """Khởi tạo các bảng trong database"""
        
        # Bảng cấu hình server
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '?',
                log_channel INTEGER,
                mod_role INTEGER
            )
        ''')

        # Bảng role tạm thời
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS temprole (
                guild_id INTEGER,
                user_id INTEGER, 
                role_id INTEGER,
                time INTEGER,
                PRIMARY KEY (guild_id, user_id, role_id)
            )
        ''')
        
        self.conn.commit()
        self.logger.info("Đã khởi tạo cấu trúc database")

    def close(self):
        """Đóng kết nối database an toàn"""
        if hasattr(self, 'conn'):
            self.conn.close()
            self.logger.info("Đã đóng kết nối database")

    def __del__(self):
        self.close()