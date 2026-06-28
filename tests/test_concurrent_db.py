import asyncio
import os
import unittest

from utils.database import Database


class DatabaseConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_temp.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_concurrent_warnings(self):
        guild_id = 12345
        user_id = 67890

        async def worker():
            for _ in range(10):
                await self.db.add_warning(guild_id, user_id)

        await asyncio.gather(*(worker() for _ in range(5)))
        total = await self.db.get_warnings(guild_id, user_id)
        self.assertEqual(total, 50)

    async def test_transaction_rollback(self):
        guild_id = 999
        user_id = 888

        try:
            async with self.db.transaction():
                await self.db.add_warning(guild_id, user_id)
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        warnings = await self.db.get_warnings(guild_id, user_id)
        self.assertEqual(warnings, 0)

    async def test_nested_transactions(self):
        guild_id = 777
        user_id = 666

        async with self.db.transaction():
            await self.db.add_warning(guild_id, user_id)
            async with self.db.transaction():
                await self.db.add_warning(guild_id, user_id)

        warnings = await self.db.get_warnings(guild_id, user_id)
        self.assertEqual(warnings, 2)

    async def test_nested_transaction_rollback(self):
        guild_id = 555
        user_id = 444

        try:
            async with self.db.transaction():
                await self.db.add_warning(guild_id, user_id)
                async with self.db.transaction():
                    await self.db.add_warning(guild_id, user_id)
                    raise RuntimeError("Inner transaction failed")
        except RuntimeError:
            pass

        warnings = await self.db.get_warnings(guild_id, user_id)
        self.assertEqual(warnings, 0)

    async def test_guild_config_cache(self):
        guild_id = 123
        config = await self.db.get_guild_config(guild_id)
        self.assertEqual(config["guild_id"], guild_id)

        await self.db.update_guild_config(guild_id, log_channel_id=999)
        updated = await self.db.get_guild_config(guild_id)
        self.assertEqual(updated["log_channel_id"], 999)

        stats = self.db.get_cache_stats()
        self.assertIn("total_entries", stats)


if __name__ == "__main__":
    unittest.main()
