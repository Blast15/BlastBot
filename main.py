import asyncio
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

if TYPE_CHECKING:
    from utils.database import Database

import contextlib

from utils.config import Config

load_dotenv()

# Setup logging với RotatingFileHandler (max 5MB x 5 backups)
rotating_handler = RotatingFileHandler(
    "bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
rotating_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[rotating_handler, logging.StreamHandler()],
)
logger = logging.getLogger("BlastBot")


class BlastBot(commands.Bot):
    """Main bot class với custom initialization và explicit typing."""

    db: Optional["Database"]
    start_time: datetime | None

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.logger = logging.getLogger("BlastBot")

        super().__init__(
            command_prefix=Config.DEFAULT_PREFIX, intents=intents, help_command=None
        )

        self.initial_extensions = self._discover_extensions()
        self.start_time = None
        self.db = None
        self._persistent_views_registered = False

    async def setup_hook(self):
        """Called when the bot is starting up"""
        logger.info("Đang tải extensions...")

        from utils.database import Database

        self.db = Database()
        await self.db.connect()

        self.tree.on_error = self.on_app_command_error

        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"✅ Đã tải {ext}")
            except Exception as e:
                logger.error(f"❌ Không thể tải {ext}: {e}")

        await self._register_persistent_views()

        gid = Config.get_guild_id_int()
        if gid:
            guild = discord.Object(id=gid)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Đã sync {len(synced)} commands cho guild {gid}")
        else:
            synced = await self.tree.sync()
            logger.info(f"Đã sync {len(synced)} commands globally")

    def _discover_modules(self, base_path: Path, package: str) -> list[str]:
        modules = []
        if not base_path.exists():
            return modules

        for item in base_path.iterdir():
            if item.name.startswith("_") or item.name.startswith("."):
                continue

            if item.is_dir():
                init_file = item / "__init__.py"
                if init_file.exists():
                    modules.append(f"{package}.{item.name}")
            elif item.is_file() and item.suffix == ".py" and item.stem != "__init__":
                modules.append(f"{package}.{item.stem}")

        return modules

    def _discover_extensions(self) -> list[str]:
        extensions = []
        base_path = Path(__file__).parent

        extensions.extend(self._discover_modules(base_path / "cogs", "cogs"))
        extensions.extend(self._discover_modules(base_path / "events", "events"))

        logger.info(
            f"Đã phát hiện {len(extensions)} extensions: {', '.join(extensions)}"
        )
        return extensions

    async def _register_persistent_views(self):
        if self._persistent_views_registered or not self.db:
            return

        try:
            from cogs.tickets.views import (
                CloseRequestView,
                TicketControlView,
                TicketPanelView,
            )
            from utils.modals import SuggestionVotingView

            self.add_view(SuggestionVotingView(self.db))
            self.add_view(TicketPanelView(self))
            self.add_view(TicketControlView(self))
            self.add_view(CloseRequestView(self))

            self._persistent_views_registered = True
            logger.info("Đã đăng ký lại persistent views")
        except Exception as e:
            logger.error(f"❌ Không thể đăng ký persistent views: {e}", exc_info=True)

    async def on_ready(self):
        if self.user:
            logger.info(f"🚀 Bot đã sẵn sàng! Đăng nhập với tên: {self.user.name}")
        logger.info(f"📊 Đang hoạt động trên {len(self.guilds)} servers")

        self.start_time = datetime.now(UTC)
        logger.info(
            f"⏰ Bot khởi động lúc: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="From Blast with love"
            )
        )

    async def close(self):
        logger.info("🛑 Đang tắt bot...")

        if getattr(self, "db", None):
            try:
                await self.db.close()
                logger.info("✅ Đã đóng database")
            except Exception as e:
                logger.error(f"❌ Lỗi khi đóng database: {e}", exc_info=True)

        await super().close()
        logger.info("✅ Bot đã tắt hoàn toàn")

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        from utils.error_handler import handle_command_error

        if isinstance(error, discord.app_commands.CommandNotFound):
            logger.warning(
                f"Command '{error.name}' không tồn tại nhưng vẫn được gọi bởi {interaction.user}."
            )
            with contextlib.suppress(
                discord.InteractionResponded, discord.HTTPException
            ):
                await interaction.response.send_message(
                    "⚠️ Lệnh này đã bị xóa. Vui lòng reload Discord (Ctrl+R) để cập nhật danh sách lệnh.",
                    ephemeral=True,
                )
            return

        original_error = getattr(error, "original", error)
        await handle_command_error(interaction, original_error)


async def main():
    token = Config.TOKEN
    if not token:
        logger.error("❌ Không tìm thấy DISCORD_TOKEN trong file .env!")
        return

    from utils.constants import BOT_CONFIG

    if not token.strip() or len(token) < BOT_CONFIG["min_token_length"]:
        logger.error("❌ DISCORD_TOKEN không hợp lệ!")
        return

    Path("data").mkdir(exist_ok=True)

    bot = BlastBot()
    async with bot:
        try:
            await bot.start(token)
        except KeyboardInterrupt:
            logger.info("⚠️ Nhận tín hiệu KeyboardInterrupt (Ctrl+C)")
        except discord.LoginFailure:
            logger.error("❌ Token không hợp lệ! Không thể đăng nhập vào Discord.")
        except Exception as e:
            logger.error(f"❌ Lỗi khi chạy bot: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("✅ Bot đã được tắt bởi người dùng")
    except Exception as e:
        logger.error(f"❌ Lỗi nghiêm trọng: {e}", exc_info=True)
