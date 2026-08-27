from __future__ import annotations

import asyncio

from blastbot.bootstrap import bootstrap
from blastbot.core.bot import BlastBot


async def _run() -> None:
    app = await bootstrap()
    bot = BlastBot(app)
    async with bot:
        await bot.start(app.settings.discord_token.get_secret_value())


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
