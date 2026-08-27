from __future__ import annotations

from dataclasses import dataclass

from blastbot.core.config import Settings
from blastbot.database.session import Database
from blastbot.modules.automation.repository import AutomationRepository
from blastbot.modules.automation.service import AutomationService
from blastbot.modules.configuration.repository import GuildConfigRepository
from blastbot.modules.configuration.service import GuildConfigService
from blastbot.modules.feedback.repository import FeedbackRepository
from blastbot.modules.feedback.service import FeedbackService
from blastbot.modules.moderation.repository import ModerationRepository
from blastbot.modules.moderation.service import ModerationService
from blastbot.modules.roles.repository import RoleMenuRepository
from blastbot.modules.roles.service import RoleMenuService
from blastbot.modules.tickets.repository import TicketRepository
from blastbot.modules.tickets.service import TicketService


@dataclass(slots=True)
class AppContext:
    settings: Settings
    database: Database
    guild_config_repo: GuildConfigRepository
    guild_config: GuildConfigService
    moderation_repo: ModerationRepository
    moderation: ModerationService
    feedback_repo: FeedbackRepository
    feedback: FeedbackService
    automation_repo: AutomationRepository
    automation: AutomationService
    tickets_repo: TicketRepository
    tickets: TicketService
    role_menus_repo: RoleMenuRepository
    role_menus: RoleMenuService


async def build_context(settings: Settings) -> AppContext:
    database = Database(settings)
    await database.initialize_schema()
    await database.ping()
    guild_config_repo = GuildConfigRepository(database)
    moderation_repo = ModerationRepository(database)
    feedback_repo = FeedbackRepository(database)
    automation_repo = AutomationRepository(database)
    tickets_repo = TicketRepository(database)
    role_menus_repo = RoleMenuRepository(database)
    return AppContext(
        settings=settings,
        database=database,
        guild_config_repo=guild_config_repo,
        guild_config=GuildConfigService(guild_config_repo),
        moderation_repo=moderation_repo,
        moderation=ModerationService(moderation_repo),
        feedback_repo=feedback_repo,
        feedback=FeedbackService(feedback_repo),
        automation_repo=automation_repo,
        automation=AutomationService(automation_repo),
        tickets_repo=tickets_repo,
        tickets=TicketService(tickets_repo),
        role_menus_repo=role_menus_repo,
        role_menus=RoleMenuService(role_menus_repo),
    )
