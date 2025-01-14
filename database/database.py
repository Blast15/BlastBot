import sqlite3
from pathlib import Path
import logging

class Database:
    """Database handler for SQLite connections and operations.
    This class manages SQLite database connections and provides methods for database operations.
    It handles the creation and management of tables for guild configurations and temporary roles.
    Attributes:
        logger (logging.Logger): Logger instance for recording database operations
        conn (sqlite3.Connection): SQLite database connection object
        cursor (sqlite3.Cursor): Database cursor for executing SQL commands
    Tables:
        guilds: Stores server configurations
            - guild_id (INTEGER): Primary key, server ID
            - prefix (TEXT): Command prefix, defaults to '?'
            - log_channel (INTEGER): Channel ID for logging
            - mod_role (INTEGER): Role ID for moderators
        temprole: Stores temporary role assignments
            - guild_id (INTEGER): Server ID
            - user_id (INTEGER): User ID
            - role_id (INTEGER): Role ID
            - time (INTEGER): Duration/expiration time
            Primary key: (guild_id, user_id, role_id)
    Raises:
        Exception: If database connection fails during initialization
    """
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
        """Sets up the database tables for the bot.
        This method initializes two tables in the SQLite database:
        - guilds: Stores server-specific configurations including guild ID, prefix, log channel, and mod role
        - temprole: Stores temporary role assignments with guild ID, user ID, role ID and duration
        The guilds table has the following columns:
            guild_id (INTEGER): Primary key, unique ID for each Discord server
            prefix (TEXT): Command prefix for the bot, defaults to '?'
            log_channel (INTEGER): ID of channel for logging bot actions
            mod_role (INTEGER): ID of moderator role
        The temprole table has the following columns:
            guild_id (INTEGER): ID of the Discord server
            user_id (INTEGER): ID of the user receiving temporary role
            role_id (INTEGER): ID of the temporary role
            time (INTEGER): Duration of the temporary role
            Primary key is composite of (guild_id, user_id, role_id)
        """
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
        """
        Safely closes the database connection.
        This method checks if a connection exists and closes it, logging the action.
        No parameters are required and nothing is returned.
        Note:
            This method uses a logger to track when the database connection is closed.
        """
        if hasattr(self, 'conn'):
            self.conn.close()
            self.logger.info("Đã đóng kết nối database")

    def __del__(self):
        self.close()