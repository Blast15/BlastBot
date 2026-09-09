from __future__ import annotations

import unittest

import discord

from blastbot.modules.configuration.cog import (
    AUTOMOD_INVITE_KEYWORDS,
    AUTOMOD_RULE_NAMES,
    ConfigurationCog,
)


class AutoModConfigurationTests(unittest.TestCase):
    def test_specs_cover_spam_mentions_and_invites(self) -> None:
        specs = ConfigurationCog._automod_specs(7)
        self.assertEqual(tuple(name for name, _ in specs), AUTOMOD_RULE_NAMES)

        spam, mentions, invites = (trigger for _, trigger in specs)
        self.assertIs(spam.type, discord.AutoModRuleTriggerType.spam)
        self.assertIs(mentions.type, discord.AutoModRuleTriggerType.mention_spam)
        self.assertEqual(mentions.mention_limit, 7)
        self.assertTrue(mentions.mention_raid_protection)
        self.assertIs(invites.type, discord.AutoModRuleTriggerType.keyword)
        self.assertEqual(tuple(invites.keyword_filter), AUTOMOD_INVITE_KEYWORDS)

    def test_actions_add_alert_only_when_configured(self) -> None:
        without_alert = ConfigurationCog._automod_actions(None)
        with_alert = ConfigurationCog._automod_actions(123)

        self.assertEqual(
            [action.type for action in without_alert],
            [discord.AutoModRuleActionType.block_message],
        )
        self.assertEqual(
            [action.type for action in with_alert],
            [
                discord.AutoModRuleActionType.block_message,
                discord.AutoModRuleActionType.send_alert_message,
            ],
        )
        self.assertEqual(with_alert[1].channel_id, 123)


if __name__ == "__main__":
    unittest.main()
