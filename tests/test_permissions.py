import unittest
from unittest.mock import AsyncMock, MagicMock

import discord
from cogs.tickets.helpers import is_blacklisted, is_ticket_staff
from cogs.tickets.views import ConfirmCloseView
from utils.error_handler import normalize_channel_name, validate_member_hierarchy


class MockRole:
    def __init__(self, position: int):
        self.position = position

    def __ge__(self, other: "MockRole") -> bool:
        return self.position >= other.position


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_is_ticket_staff_admin_perm(self):
        bot = MagicMock()
        member = MagicMock(spec=discord.Member)
        member.guild_permissions.administrator = True
        member.guild_permissions.manage_guild = False

        res = await is_ticket_staff(bot, member)
        self.assertTrue(res)

    async def test_is_ticket_staff_by_role_and_user(self):
        bot = MagicMock()
        db = AsyncMock()
        bot.db = db

        db.get_staff.return_value = [
            {"is_role": True, "entity_id": 100},
            {"is_role": False, "entity_id": 999},
        ]

        role1 = MagicMock()
        role1.id = 100
        member1 = MagicMock(spec=discord.Member)
        member1.id = 500
        member1.guild_permissions.administrator = False
        member1.guild_permissions.manage_guild = False
        member1.roles = [role1]
        member1.guild.id = 1

        self.assertTrue(await is_ticket_staff(bot, member1))

        member2 = MagicMock(spec=discord.Member)
        member2.id = 999
        member2.guild_permissions.administrator = False
        member2.guild_permissions.manage_guild = False
        member2.roles = []
        member2.guild.id = 1

        self.assertTrue(await is_ticket_staff(bot, member2))

        member3 = MagicMock(spec=discord.Member)
        member3.id = 888
        member3.guild_permissions.administrator = False
        member3.guild_permissions.manage_guild = False
        member3.roles = []
        member3.guild.id = 1

        self.assertFalse(await is_ticket_staff(bot, member3))

    async def test_is_blacklisted(self):
        bot = MagicMock()
        db = AsyncMock()
        bot.db = db
        db.get_blacklist.return_value = [{"is_role": False, "entity_id": 777}]

        bad_member = MagicMock(spec=discord.Member)
        bad_member.id = 777
        bad_member.roles = []
        bad_member.guild.id = 1
        bad_member.guild_permissions.administrator = False

        self.assertTrue(await is_blacklisted(bot, bad_member))

        admin_member = MagicMock(spec=discord.Member)
        admin_member.id = 777
        admin_member.roles = []
        admin_member.guild.id = 1
        admin_member.guild_permissions.administrator = True
        self.assertFalse(await is_blacklisted(bot, admin_member))

    def test_validate_member_hierarchy(self):
        mod = MagicMock(spec=discord.Member)
        target = MagicMock(spec=discord.Member)
        bot_member = MagicMock(spec=discord.Member)

        mod.top_role = MockRole(10)
        bot_member.top_role = MockRole(10)
        target.top_role = MockRole(5)

        valid, msg = validate_member_hierarchy(mod, target, bot_member)
        self.assertTrue(valid)
        self.assertIsNone(msg)

        target.top_role = MockRole(10)
        valid, msg = validate_member_hierarchy(mod, target, bot_member)
        self.assertFalse(valid)

    async def test_confirm_close_view_interaction_check(self):
        bot = MagicMock()
        db = AsyncMock()
        bot.db = db

        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel = MagicMock(spec=discord.TextChannel)
        interaction.channel.id = 1001

        user = MagicMock(spec=discord.Member)
        user.id = 55
        interaction.user = user
        interaction.response.send_message = AsyncMock()

        db.get_ticket_by_channel.return_value = {
            "owner_id": 99,
            "number": 1,
        }
        db.get_staff.return_value = []

        view = ConfirmCloseView(bot=bot, requester_id=55)
        # Allowed because user is requester (55)
        allowed = await view.interaction_check(interaction)
        self.assertTrue(allowed)

        # Non-requester, non-owner, non-staff user
        user2 = MagicMock(spec=discord.Member)
        user2.id = 888
        user2.guild_permissions.administrator = False
        user2.guild_permissions.manage_guild = False
        user2.roles = []
        interaction.user = user2

        allowed2 = await view.interaction_check(interaction)
        self.assertFalse(allowed2)

    def test_normalize_channel_name(self):
        self.assertEqual(
            normalize_channel_name("  Ticket #123 (Help)  "), "ticket-123-help"
        )
        self.assertEqual(normalize_channel_name("!!!"), "ticket")
