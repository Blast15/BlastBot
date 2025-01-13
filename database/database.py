import sqlite3
from pathlib import Path

class Database:
    def __init__(self):
        # Create database directory if it doesn't exist
        db_dir = Path('./database')
        db_dir.mkdir(exist_ok=True)
        
        # Connect to SQLite database (creates if not exists)
        self.conn = sqlite3.connect('./database/bot.db')
        self.cursor = self.conn.cursor()
        self.setup()

    def setup(self):
        """Create initial tables"""
        # Example table creation
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            prefix TEXT DEFAULT '$',
            log_channel INTEGER,
            welcome_channel INTEGER,
            mod_role INTEGER,
            admin_role INTEGER,
            auto_role INTEGER,
            welcome_message TEXT
        )
        ''')
        self.conn.commit()
    
    def close(self):
        """Close database connection"""
        self.conn.close()

    def __del__(self):
        """Destructor to ensure connection is closed"""
        self.close()