from __future__ import annotations

from dataclasses import dataclass

from blastbot.core.config import Settings
from blastbot.database.session import Database
from blastbot.modules.automation.repository import AutomationRepository
from blastbot.modules.automation.service import AutomationService
from blastbot.modules.configuration.repository import GuildConfigRepository
from blastbot.modules.configuration.service import GuildConfigService
from blastbot.modules.moderation.repository import ModerationRepository
from blastbot.modules.moderation.service import ModerationService
from blastbot.modules.reddit.repository import RedditRepository
from blastbot.modules.reddit.service import RedditService
from blastbot.modules.roles.repository import RoleMenuRepository
from blastbot.modules.roles.service import RoleMenuService


@dataclass(slots=True)
class AppContext:
    settings: Settings
    database: Database
    guild_config_repo: GuildConfigRepository
    guild_config: GuildConfigService
    moderation_repo: ModerationRepository
    moderation: ModerationService
    automation_repo: AutomationRepository
    automation: AutomationService
    role_menus_repo: RoleMenuRepository
    role_menus: RoleMenuService
    reddit_repo: RedditRepository
    reddit: RedditService


async def build_context(settings: Settings) -> AppContext:
    database = Database(settings)
    await database.initialize_schema()
    await database.ping()
    guild_config_repo = GuildConfigRepository(database)
    moderation_repo = ModerationRepository(database)
    automation_repo = AutomationRepository(database)
    role_menus_repo = RoleMenuRepository(database)
    reddit_repo = RedditRepository(database)
    return AppContext(
        settings=settings,
        database=database,
        guild_config_repo=guild_config_repo,
        guild_config=GuildConfigService(guild_config_repo),
        moderation_repo=moderation_repo,
        moderation=ModerationService(moderation_repo),
        automation_repo=automation_repo,
        automation=AutomationService(automation_repo),
        role_menus_repo=role_menus_repo,
        role_menus=RoleMenuService(role_menus_repo),
        reddit_repo=reddit_repo,
        reddit=RedditService(reddit_repo),
    )
