"""Database helper cho SQLite"""

import aiosqlite
import os
from typing import Optional, Dict
import logging
from utils.error_handler import DatabaseError
from datetime import datetime, timedelta

logger = logging.getLogger('BlastBot.Database')
# Ngăn logger của Database ghi ra console thông qua root logger
# và đảm bảo vẫn ghi vào file log chung.
if not logger.handlers:
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class Database:
    """Wrapper cho aiosqlite database operations với caching"""
    
    # Class-level cache cho guild configs
    _guild_config_cache: Dict[int, dict] = {}
    _cache_timestamps: Dict[int, datetime] = {}
    _cache_ttl = timedelta(minutes=5)  # Cache TTL: 5 minutes
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv('DB_PATH', './data/bot.db')
        self.conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Kết nối đến database"""
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            if self.conn:
                self.conn.row_factory = aiosqlite.Row
                await self.initialize_tables()
            logger.info(f"Database connected: {self.db_path}")
        except aiosqlite.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise DatabaseError(f"Database connection failed: {e}")
    
    async def close(self):
        """Đóng kết nối database"""
        if self.conn:
            try:
                await self.conn.close()
                logger.info("Database connection closed")
            except aiosqlite.Error as e:
                logger.error(f"Error closing database: {e}")
    
    async def initialize_tables(self):
        """Tạo tables nếu chưa tồn tại"""
        if not self.conn:
            return
        
        try:
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id INTEGER PRIMARY KEY,
                    prefix TEXT DEFAULT '!',
                    welcome_channel_id INTEGER,
                    log_channel_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    points INTEGER DEFAULT 0,
                    warnings INTEGER DEFAULT 0,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
                )
            """)
            
            await self.conn.commit()
            logger.info("Database tables initialized")
        except aiosqlite.Error as e:
            logger.error(f"Failed to initialize tables: {e}")
            raise DatabaseError(f"Table initialization failed: {e}")
    
    async def get_guild_config(self, guild_id: int) -> dict:
        """Lấy config của guild (with caching)"""
        # Check cache first
        if guild_id in self._guild_config_cache:
            cache_time = self._cache_timestamps.get(guild_id)
            if cache_time and datetime.utcnow() - cache_time < self._cache_ttl:
                logger.debug(f"Cache hit for guild {guild_id}")
                return self._guild_config_cache[guild_id].copy()
        
        default_config = {
            'guild_id': guild_id,
            'prefix': '!',
            'welcome_channel_id': None,
            'log_channel_id': None
        }
        
        if not self.conn:
            return default_config
        
        try:
            async with self.conn.execute(
                "SELECT * FROM guilds WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    config = dict(row)
                    # Update cache
                    self._guild_config_cache[guild_id] = config.copy()
                    self._cache_timestamps[guild_id] = datetime.utcnow()
                    return config
                else:
                    # Tạo config mới nếu chưa có
                    await self.conn.execute(
                        "INSERT INTO guilds (guild_id) VALUES (?)",
                        (guild_id,)
                    )
                    await self.conn.commit()
                    # Cache default config
                    self._guild_config_cache[guild_id] = default_config.copy()
                    self._cache_timestamps[guild_id] = datetime.utcnow()
                    return default_config
        except aiosqlite.Error as e:
            logger.error(f"Failed to get guild config for {guild_id}: {e}")
            return default_config
    
    async def update_guild_config(self, guild_id: int, **kwargs):
        """Cập nhật config của guild (invalidates cache)"""
        if not self.conn:
            return
        
        valid_fields = ['prefix', 'welcome_channel_id', 'log_channel_id']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if not updates:
            return
        
        try:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [guild_id]
            
            await self.conn.execute(
                f"UPDATE guilds SET {set_clause} WHERE guild_id = ?",
                values
            )
            await self.conn.commit()
            
            # Invalidate cache
            self.invalidate_cache(guild_id)
            
            logger.debug(f"Updated guild config for {guild_id}: {updates}")
        except aiosqlite.Error as e:
            logger.error(f"Failed to update guild config for {guild_id}: {e}")
            await self.conn.rollback()
            raise DatabaseError(f"Failed to update guild config: {e}")
    
    @classmethod
    def invalidate_cache(cls, guild_id: Optional[int] = None):
        """
        Invalidate cache for specific guild or all guilds
        
        Args:
            guild_id: Guild ID to invalidate (None = invalidate all)
        """
        if guild_id is None:
            cls._guild_config_cache.clear()
            cls._cache_timestamps.clear()
            logger.debug("Cleared all guild config cache")
        elif guild_id in cls._guild_config_cache:
            del cls._guild_config_cache[guild_id]
            if guild_id in cls._cache_timestamps:
                del cls._cache_timestamps[guild_id]
            logger.debug(f"Invalidated cache for guild {guild_id}")
    
    @classmethod
    def get_cache_stats(cls) -> dict:
        """Get cache statistics"""
        current_time = datetime.utcnow()
        valid_entries = sum(
            1 for guild_id, timestamp in cls._cache_timestamps.items()
            if current_time - timestamp < cls._cache_ttl
        )
        
        return {
            'total_entries': len(cls._guild_config_cache),
            'valid_entries': valid_entries,
            'expired_entries': len(cls._guild_config_cache) - valid_entries,
            'ttl_seconds': cls._cache_ttl.total_seconds()
        }
    
    async def get_user_data(self, user_id: int, guild_id: int) -> dict:
        """Lấy dữ liệu user"""
        default_data = {
            'user_id': user_id,
            'guild_id': guild_id,
            'points': 0,
            'warnings': 0
        }
        
        if not self.conn:
            return default_data
        
        try:
            async with self.conn.execute(
                "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                else:
                    # Tạo user mới nếu chưa có
                    await self.conn.execute(
                        "INSERT INTO users (user_id, guild_id) VALUES (?, ?)",
                        (user_id, guild_id)
                    )
                    await self.conn.commit()
                    return default_data
        except aiosqlite.Error as e:
            logger.error(f"Failed to get user data for {user_id} in guild {guild_id}: {e}")
            return default_data
    
    async def update_user_data(self, user_id: int, guild_id: int, **kwargs):
        """Cập nhật dữ liệu user"""
        if not self.conn:
            return
        
        valid_fields = ['points', 'warnings', 'last_active']
        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if not updates:
            return
        
        try:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [user_id, guild_id]
            
            await self.conn.execute(
                f"UPDATE users SET {set_clause} WHERE user_id = ? AND guild_id = ?",
                values
            )
            await self.conn.commit()
            logger.debug(f"Updated user data for {user_id} in guild {guild_id}: {updates}")
        except aiosqlite.Error as e:
            logger.error(f"Failed to update user data for {user_id} in guild {guild_id}: {e}")
            await self.conn.rollback()
            raise DatabaseError(f"Failed to update user data: {e}")
