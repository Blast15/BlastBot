import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Cấu hình tập trung cho bot với helper validation."""

    TOKEN: Optional[str] = os.getenv("DISCORD_TOKEN")
    DEFAULT_PREFIX: str = os.getenv("BOT_PREFIX", "!")
    DB_PATH: str = os.getenv("DB_PATH", "./data/bot.db")
    GUILD_ID: Optional[str] = os.getenv("GUILD_ID") or None
    OWNER_ID: Optional[str] = os.getenv("OWNER_ID") or None

    @classmethod
    def get_guild_id_int(cls) -> Optional[int]:
        if cls.GUILD_ID and cls.GUILD_ID.strip():
            try:
                return int(cls.GUILD_ID.strip())
            except ValueError:
                return None
        return None

    @classmethod
    def get_owner_id_int(cls) -> Optional[int]:
        if cls.OWNER_ID and cls.OWNER_ID.strip():
            try:
                return int(cls.OWNER_ID.strip())
            except ValueError:
                return None
        return None