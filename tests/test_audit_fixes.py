import os
import unittest

from utils.database import Database


class AuditFixesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_audit_fixes_temp.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_guild_config_cache_copy(self):
        guild_id = 777
        config1 = await self.db.get_guild_config(guild_id)
        config1["log_channel_id"] = 9999
        config2 = await self.db.get_guild_config(guild_id)
        self.assertIsNone(config2["log_channel_id"])

    async def test_create_panel_and_ticket_return_int(self):
        guild_id = 888
        panel_id = await self.db.create_panel(
            guild_id,
            title="Support",
            content="Click button",
            color=0xFFFFFF,
            category_id=123,
            button_label="Open",
        )
        self.assertIsInstance(panel_id, int)
        self.assertGreater(panel_id, 0)

        ticket_id = await self.db.create_ticket(
            guild_id, number=1, channel_id=456, owner_id=123, panel_id=panel_id
        )
        self.assertIsInstance(ticket_id, int)
        self.assertGreater(ticket_id, 0)

    async def test_ticket_members_crud(self):
        channel_id = 999
        user_id = 12345

        # Initial state should be empty
        members = await self.db.get_ticket_members(channel_id)
        self.assertEqual(members, [])

        # Add member
        await self.db.add_ticket_member(channel_id, user_id)
        members = await self.db.get_ticket_members(channel_id)
        self.assertEqual(members, [user_id])

        # Remove member
        removed = await self.db.remove_ticket_member(channel_id, user_id)
        self.assertTrue(removed)
        members = await self.db.get_ticket_members(channel_id)
        self.assertEqual(members, [])
