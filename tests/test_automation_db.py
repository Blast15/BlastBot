import os
import unittest

from utils.database import Database


class AutomationDBTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_auto_temp.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_greeting_roundtrip(self):
        await self.db.set_greeting(1, "welcome", enabled=1, channel_id=99, message="hi")
        cfg = await self.db.get_greeting(1, "welcome")
        self.assertEqual(cfg["enabled"], 1)
        self.assertEqual(cfg["channel_id"], 99)

    async def test_auto_message_due(self):
        aid = await self.db.create_auto_message(1, 99, "ping", 5)
        due = await self.db.get_due_auto_messages()  # chưa gửi → due ngay
        self.assertTrue(any(m["id"] == aid for m in due))
        await self.db.mark_auto_message_sent(aid)
        due_after = await self.db.get_due_auto_messages()  # vừa gửi → chưa due
        self.assertFalse(any(m["id"] == aid for m in due_after))
