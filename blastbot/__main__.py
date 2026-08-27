from __future__ import annotations

import asyncio
import signal
from contextlib import suppress

from blastbot.bootstrap import bootstrap
from blastbot.core.bot import BlastBot


async def _run() -> None:
    app = await bootstrap()
    bot = BlastBot(app)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signum, stop.set)

    async with bot:
        bot_task = asyncio.create_task(
            bot.start(app.settings.discord_token.get_secret_value()),
            name="discord-bot",
        )
        stop_task = asyncio.create_task(stop.wait(), name="shutdown-signal")
        try:
            done, _ = await asyncio.wait((bot_task, stop_task), return_when=asyncio.FIRST_COMPLETED)
            if bot_task in done:
                await bot_task
            else:
                bot_task.cancel()
                with suppress(asyncio.CancelledError):
                    await bot_task
        finally:
            stop_task.cancel()
            with suppress(asyncio.CancelledError):
                await stop_task


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
