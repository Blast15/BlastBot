import unittest
import os
from utils.database import Database


class TicketDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_ticket_temp.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_ticket_settings(self):
        guild_id = 1001
        settings = await self.db.get_ticket_settings(guild_id)
        self.assertEqual(settings['ticket_limit'], 5)

        await self.db.update_ticket_settings(guild_id, ticket_limit=10, autoclose_hours=24)
        updated = await self.db.get_ticket_settings(guild_id)
        self.assertEqual(updated['ticket_limit'], 10)
        self.assertEqual(updated['autoclose_hours'], 24)

    async def test_ticket_counter_and_creation(self):
        guild_id = 2002
        num1 = await self.db.next_ticket_number(guild_id)
        num2 = await self.db.next_ticket_number(guild_id)
        self.assertEqual(num1, 1)
        self.assertEqual(num2, 2)

        ticket_id = await self.db.create_ticket(guild_id, num1, channel_id=5555, owner_id=999, panel_id=None)
        self.assertGreater(ticket_id, 0)

        t_data = await self.db.get_ticket_by_channel(5555)
        self.assertIsNotNone(t_data)
        self.assertEqual(t_data['number'], 1)
        self.assertEqual(t_data['owner_id'], 999)

        count = await self.db.count_open_tickets(guild_id, 999)
        self.assertEqual(count, 1)

    async def test_staff_and_blacklist(self):
        guild_id = 3003
        await self.db.add_staff(guild_id, entity_id=888, is_role=False, type_="support")
        staff = await self.db.get_staff(guild_id)
        self.assertEqual(len(staff), 1)

        await self.db.set_blacklist(guild_id, entity_id=777, is_role=False, blacklisted=True)
        bl = await self.db.get_blacklist(guild_id)
        self.assertEqual(len(bl), 1)

    async def test_tags(self):
        guild_id = 4004
        await self.db.add_tag(guild_id, "rules", "Be nice!")
        tag = await self.db.get_tag(guild_id, "RULES")
        self.assertEqual(tag, "Be nice!")

        tags_list = await self.db.list_tags(guild_id)
        self.assertIn("rules", tags_list)


if __name__ == "__main__":
    unittest.main()
