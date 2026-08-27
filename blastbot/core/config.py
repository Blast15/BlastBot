from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SyncMode(StrEnum):
    NONE = "none"
    DEV_GUILD = "dev_guild"
    GLOBAL = "global"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    discord_token: SecretStr = Field(alias="DISCORD_TOKEN")
    owner_id: int | None = Field(default=None, alias="OWNER_ID")
    dev_guild_id: int | None = Field(default=None, alias="DEV_GUILD_ID")
    database_url: str = Field(default="sqlite+aiosqlite:///./data/bot.db", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
    sync_mode: SyncMode = Field(default=SyncMode.NONE, alias="SYNC_MODE")
    reddit_client_id: str | None = Field(default=None, alias="REDDIT_CLIENT_ID")
    reddit_client_secret: SecretStr | None = Field(default=None, alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(
        default="BlastBot Discord Reddit monitor by Blast15", alias="REDDIT_USER_AGENT"
    )
    reddit_poll_interval: int = Field(default=120, alias="REDDIT_POLL_INTERVAL", ge=60, le=3600)
    reddit_keyless_fallback: bool = Field(default=True, alias="REDDIT_KEYLESS_FALLBACK")

    feature_moderation: bool = Field(default=True, alias="FEATURE_MODERATION")
    feature_automation: bool = Field(default=True, alias="FEATURE_AUTOMATION")
    feature_roles: bool = Field(default=True, alias="FEATURE_ROLES")
    feature_context_menus: bool = Field(default=True, alias="FEATURE_CONTEXT_MENUS")
    feature_reddit: bool = Field(default=True, alias="FEATURE_REDDIT")

    @field_validator("owner_id", "dev_guild_id", mode="before")
    @classmethod
    def empty_optional_id(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("discord_token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().strip()) < 40:
            raise ValueError("DISCORD_TOKEN appears invalid or empty")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper().strip()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite+")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.model_validate({})
