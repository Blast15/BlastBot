from __future__ import annotations

from blastbot.core.config import Settings


def enabled_extensions(settings: Settings) -> tuple[str, ...]:
    extensions: list[str] = ["blastbot.modules.help.cog", "blastbot.modules.configuration.cog"]
    if settings.feature_moderation:
        extensions.append("blastbot.modules.moderation.cog")
    if settings.feature_roles:
        extensions.append("blastbot.modules.roles.cog")
    if settings.feature_feedback:
        extensions.append("blastbot.modules.feedback.cog")
    if settings.feature_automation:
        extensions.append("blastbot.modules.automation.cog")
    if settings.feature_tickets:
        extensions.append("blastbot.modules.tickets.cog")
    if settings.feature_context_menus:
        extensions.append("blastbot.modules.interactions.cog")
    if settings.feature_reddit:
        extensions.append("blastbot.modules.reddit.cog")
    return tuple(extensions)
