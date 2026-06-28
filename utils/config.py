import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Cấu hình tập trung cho bot với helper validation."""

    TOKEN: str | None = os.getenv("DISCORD_TOKEN")
    DEFAULT_PREFIX: str = os.getenv("BOT_PREFIX", "!")
    DB_PATH: str = os.getenv("DB_PATH", "./data/bot.db")
    GUILD_ID: str | None = os.getenv("GUILD_ID") or None
    OWNER_ID: str | None = os.getenv("OWNER_ID") or None

    @classmethod
    def get_guild_id_int(cls) -> int | None:
        if cls.GUILD_ID and cls.GUILD_ID.strip():
            try:
                return int(cls.GUILD_ID.strip())
            except ValueError:
                return None
        return None

    @classmethod
    def get_owner_id_int(cls) -> int | None:
        if cls.OWNER_ID and cls.OWNER_ID.strip():
            try:
                return int(cls.OWNER_ID.strip())
            except ValueError:
                return None
        return None
