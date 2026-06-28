"""Database mixin cho hệ thống automation (welcome/goodbye/auto-message)."""


class AutomationDBMixin:
    # ---------- bảng ----------
    async def init_automation_tables(self):
        if not self.conn:
            return
        c = self.conn
        # Cấu hình welcome/goodbye mỗi guild
        await c.execute("""
            CREATE TABLE IF NOT EXISTS automation_greetings (
                guild_id INTEGER NOT NULL,
                kind TEXT NOT NULL,                 -- 'welcome' | 'goodbye'
                enabled INTEGER NOT NULL DEFAULT 0,
                channel_id INTEGER,
                use_embed INTEGER NOT NULL DEFAULT 1,
                title TEXT,
                message TEXT,                        -- hỗ trợ placeholder
                color INTEGER,
                PRIMARY KEY (guild_id, kind))""")
        # Auto-message lặp lại theo chu kỳ
        await c.execute("""
            CREATE TABLE IF NOT EXISTS auto_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL,
                use_embed INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_sent TIMESTAMP)""")
        await c.execute(
            "CREATE INDEX IF NOT EXISTS idx_auto_messages_guild ON auto_messages(guild_id)"
        )
        await self._commit_if_not_in_tx()

    # ---------- greetings (welcome/goodbye) ----------
    async def get_greeting(self, guild_id: int, kind: str) -> dict:
        async with self._lock:
            default = {
                "guild_id": guild_id,
                "kind": kind,
                "enabled": 0,
                "channel_id": None,
                "use_embed": 1,
                "title": None,
                "message": None,
                "color": None,
            }
            if not self.conn:
                return default
            async with self.conn.execute(
                "SELECT * FROM automation_greetings WHERE guild_id=? AND kind=?",
                (guild_id, kind),
            ) as cur:
                row = await cur.fetchone()
            return dict(row) if row else default

    async def set_greeting(self, guild_id: int, kind: str, **kwargs):
        async with self._lock:
            if not self.conn:
                return
            valid = ["enabled", "channel_id", "use_embed", "title", "message", "color"]
            updates = {k: v for k, v in kwargs.items() if k in valid}
            if not updates:
                return
            # Đảm bảo có row trước khi update
            await self.conn.execute(
                "INSERT OR IGNORE INTO automation_greetings (guild_id, kind) VALUES (?, ?)",
                (guild_id, kind),
            )
            clause = ", ".join(f"{k}=?" for k in updates)
            await self.conn.execute(
                f"UPDATE automation_greetings SET {clause} WHERE guild_id=? AND kind=?",
                list(updates.values()) + [guild_id, kind],
            )
            await self._commit_if_not_in_tx()

    # ---------- auto messages ----------
    async def create_auto_message(
        self,
        guild_id: int,
        channel_id: int,
        content: str,
        interval_minutes: int,
        use_embed: bool = False,
    ) -> int:
        async with self._lock:
            if not self.conn:
                return 0
            cur = await self.conn.execute(
                """INSERT INTO auto_messages
                   (guild_id, channel_id, content, interval_minutes, use_embed)
                   VALUES (?,?,?,?,?)""",
                (guild_id, channel_id, content, interval_minutes, int(use_embed)),
            )
            await self._commit_if_not_in_tx()
            return cur.lastrowid or 0

    async def list_auto_messages(self, guild_id: int) -> list[dict]:
        async with self._lock:
            if not self.conn:
                return []
            async with self.conn.execute(
                "SELECT * FROM auto_messages WHERE guild_id=?", (guild_id,)
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def delete_auto_message(self, guild_id: int, auto_id: int) -> bool:
        async with self._lock:
            if not self.conn:
                return False
            cur = await self.conn.execute(
                "DELETE FROM auto_messages WHERE id=? AND guild_id=?",
                (auto_id, guild_id),
            )
            await self._commit_if_not_in_tx()
            return cur.rowcount > 0

    async def toggle_auto_message(
        self, guild_id: int, auto_id: int, enabled: bool
    ) -> bool:
        async with self._lock:
            if not self.conn:
                return False
            cur = await self.conn.execute(
                "UPDATE auto_messages SET enabled=? WHERE id=? AND guild_id=?",
                (int(enabled), auto_id, guild_id),
            )
            await self._commit_if_not_in_tx()
            return cur.rowcount > 0

    async def get_due_auto_messages(self) -> list[dict]:
        """Trả auto-message đang bật, chưa gửi lần nào hoặc đã quá chu kỳ."""
        async with self._lock:
            if not self.conn:
                return []
            async with self.conn.execute(
                """SELECT * FROM auto_messages
                   WHERE enabled=1
                     AND (last_sent IS NULL
                          OR julianday('now') - julianday(last_sent)
                             > (interval_minutes / 1440.0))"""
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def mark_auto_message_sent(self, auto_id: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "UPDATE auto_messages SET last_sent=datetime('now') WHERE id=?",
                (auto_id,),
            )
            await self._commit_if_not_in_tx()
