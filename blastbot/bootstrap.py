from __future__ import annotations

from blastbot.core.config import get_settings
from blastbot.core.context import AppContext, build_context
from blastbot.core.logging import configure_logging


async def bootstrap() -> AppContext:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)
    return await build_context(settings)
