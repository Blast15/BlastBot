from __future__ import annotations

import logging
from datetime import UTC, datetime

import discord
from discord.ext import commands

from blastbot import __version__
from blastbot.core.config import SyncMode
from blastbot.core.context import AppContext
from blastbot.core.error_handler import handle_app_command_error
from blastbot.core.extensions import enabled_extensions

logger = logging.getLogger(__name__)


class BlastBot(commands.Bot):
    def __init__(self, app: AppContext) -> None:
        intents = discord.Intents.default()
        # Required by greeting/role hierarchy features and current compatibility behavior.
        intents.members = True
        # Ticket inactivity tracking currently observes on_message; content itself is not required.
        intents.message_content = False
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            owner_id=app.settings.owner_id,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, roles=False, users=True, replied_user=False
            ),
        )
        self.app = app
        self.started_at = datetime.now(UTC)

    async def setup_hook(self) -> None:
        self.tree.on_error = handle_app_command_error
        for extension in enabled_extensions(self.app.settings):
            await self.load_extension(extension)
            logger.info("Loaded extension %s", extension)

        # Persistent component callbacks are registered once at process startup.
        if self.app.settings.feature_feedback:
            from blastbot.modules.feedback.ui import SuggestionVotingView

            self.add_view(SuggestionVotingView(self.app.feedback))
        if self.app.settings.feature_roles:
            from blastbot.modules.roles.ui import RoleMenuView

            self.add_view(RoleMenuView(self))
        if self.app.settings.feature_tickets:
            from blastbot.modules.tickets.ui import (
                CloseRequestView,
                TicketControlView,
                TicketPanelView,
            )

            self.add_view(TicketPanelView(self))
            self.add_view(TicketControlView(self))
            self.add_view(CloseRequestView(self))

        if self.app.settings.sync_mode is SyncMode.DEV_GUILD:
            guild_id = self.app.settings.dev_guild_id
            if guild_id is None:
                raise RuntimeError("SYNC_MODE=dev_guild requires DEV_GUILD_ID")
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d development guild commands", len(synced))
        elif self.app.settings.sync_mode is SyncMode.GLOBAL:
            synced = await self.tree.sync()
            logger.warning(
                "Explicit global command sync completed: %d commands", len(synced)
            )

    async def on_ready(self) -> None:
        if self.user is None:
            return
        logger.info(
            "Bot ready as %s (%s), guilds=%d", self.user, self.user.id, len(self.guilds)
        )
        await self.change_presence(
            activity=discord.Game(name=f"/help | BlastBot v{__version__}"),
            status=discord.Status.online,
        )

    async def on_error(
        self, event_method: str, *args: object, **kwargs: object
    ) -> None:
        logger.exception(
            "Unhandled Discord event listener error",
            extra={"operation": event_method, "error_type": "event_listener"},
        )

    async def close(self) -> None:
        logger.info("Bot shutdown started")
        try:
            await super().close()
        finally:
            await self.app.database.dispose()
            logger.info("Bot shutdown complete")
