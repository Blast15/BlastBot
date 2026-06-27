"""Database mixin cho hệ thống ticket. Dùng chung self.conn, self._lock, self._commit_if_not_in_tx."""

import json
from typing import Optional
from datetime import datetime, timezone


class TicketDBMixin:
    # ---------- bảng ----------
    async def init_ticket_tables(self):
        if not self.conn:
            return
        c = self.conn
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ticket_settings (
                guild_id INTEGER PRIMARY KEY,
                transcript_channel_id INTEGER,
                ticket_limit INTEGER NOT NULL DEFAULT 5,
                welcome_message TEXT,
                claim_mode TEXT NOT NULL DEFAULT 'reply_only',
                autoclose_hours INTEGER NOT NULL DEFAULT 0,
                ticket_counter INTEGER NOT NULL DEFAULT 0
            )""")
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ticket_staff (
                guild_id INTEGER NOT NULL, entity_id INTEGER NOT NULL,
                is_role INTEGER NOT NULL, type TEXT NOT NULL,
                PRIMARY KEY (guild_id, entity_id, type))""")
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ticket_panels (
                panel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                color INTEGER NOT NULL, category_id INTEGER NOT NULL,
                button_label TEXT NOT NULL, button_emoji TEXT,
                welcome_message TEXT,
                mention_on_open TEXT NOT NULL DEFAULT '[]',
                message_id INTEGER, channel_id INTEGER)""")
        await c.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL, number INTEGER NOT NULL,
                channel_id INTEGER, owner_id INTEGER NOT NULL, panel_id INTEGER,
                claimed_by INTEGER, open INTEGER NOT NULL DEFAULT 1,
                open_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                close_time TIMESTAMP, close_reason TEXT,
                last_message_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                excluded_autoclose INTEGER NOT NULL DEFAULT 0)""")
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ticket_members (
                channel_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                PRIMARY KEY (channel_id, user_id))""")
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ticket_blacklist (
                guild_id INTEGER NOT NULL, entity_id INTEGER NOT NULL,
                is_role INTEGER NOT NULL, PRIMARY KEY (guild_id, entity_id))""")
        await c.execute("""
            CREATE TABLE IF NOT EXISTS ticket_tags (
                guild_id INTEGER NOT NULL, tag_id TEXT NOT NULL, content TEXT NOT NULL,
                PRIMARY KEY (guild_id, tag_id))""")
        await c.execute("CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(channel_id)")
        await self._commit_if_not_in_tx()

    # ---------- settings ----------
    async def get_ticket_settings(self, guild_id: int) -> dict:
        async with self._lock:
            default = {
                'guild_id': guild_id, 'transcript_channel_id': None, 'ticket_limit': 5,
                'welcome_message': None, 'claim_mode': 'reply_only',
                'autoclose_hours': 0, 'ticket_counter': 0,
            }
            if not self.conn:
                return default
            async with self.conn.execute(
                "SELECT * FROM ticket_settings WHERE guild_id = ?", (guild_id,)) as cur:
                row = await cur.fetchone()
            if row:
                return dict(row)
            await self.conn.execute(
                "INSERT INTO ticket_settings (guild_id) VALUES (?)", (guild_id,))
            await self._commit_if_not_in_tx()
            return default

    async def update_ticket_settings(self, guild_id: int, **kwargs):
        async with self._lock:
            if not self.conn:
                return
            valid = ['transcript_channel_id', 'ticket_limit', 'welcome_message',
                     'claim_mode', 'autoclose_hours']
            updates = {k: v for k, v in kwargs.items() if k in valid}
            if not updates:
                return
            await self.conn.execute(
                "INSERT OR IGNORE INTO ticket_settings (guild_id) VALUES (?)", (guild_id,))
            clause = ", ".join(f"{k} = ?" for k in updates)
            await self.conn.execute(
                f"UPDATE ticket_settings SET {clause} WHERE guild_id = ?",
                list(updates.values()) + [guild_id])
            await self._commit_if_not_in_tx()

    async def next_ticket_number(self, guild_id: int) -> int:
        async with self._lock:
            if not self.conn:
                return 0
            await self.conn.execute(
                "INSERT OR IGNORE INTO ticket_settings (guild_id) VALUES (?)", (guild_id,))
            await self.conn.execute(
                "UPDATE ticket_settings SET ticket_counter = ticket_counter + 1 WHERE guild_id = ?",
                (guild_id,))
            await self._commit_if_not_in_tx()
            async with self.conn.execute(
                "SELECT ticket_counter FROM ticket_settings WHERE guild_id = ?", (guild_id,)) as cur:
                row = await cur.fetchone()
            return row[0] if row else 0

    # ---------- staff ----------
    async def add_staff(self, guild_id: int, entity_id: int, is_role: bool, type_: str):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "INSERT OR REPLACE INTO ticket_staff (guild_id, entity_id, is_role, type) VALUES (?,?,?,?)",
                (guild_id, entity_id, int(is_role), type_))
            await self._commit_if_not_in_tx()

    async def remove_staff(self, guild_id: int, entity_id: int, type_: str):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "DELETE FROM ticket_staff WHERE guild_id=? AND entity_id=? AND type=?",
                (guild_id, entity_id, type_))
            await self._commit_if_not_in_tx()

    async def get_staff(self, guild_id: int) -> list[dict]:
        async with self._lock:
            if not self.conn:
                return []
            async with self.conn.execute(
                "SELECT * FROM ticket_staff WHERE guild_id=?", (guild_id,)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ---------- blacklist ----------
    async def set_blacklist(self, guild_id: int, entity_id: int, is_role: bool, blacklisted: bool):
        async with self._lock:
            if not self.conn:
                return
            if blacklisted:
                await self.conn.execute(
                    "INSERT OR REPLACE INTO ticket_blacklist (guild_id, entity_id, is_role) VALUES (?,?,?)",
                    (guild_id, entity_id, int(is_role)))
            else:
                await self.conn.execute(
                    "DELETE FROM ticket_blacklist WHERE guild_id=? AND entity_id=?",
                    (guild_id, entity_id))
            await self._commit_if_not_in_tx()

    async def get_blacklist(self, guild_id: int) -> list[dict]:
        async with self._lock:
            if not self.conn:
                return []
            async with self.conn.execute(
                "SELECT * FROM ticket_blacklist WHERE guild_id=?", (guild_id,)) as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ---------- panels ----------
    async def create_panel(self, guild_id: int, **data) -> int:
        async with self._lock:
            if not self.conn:
                return 0
            cur = await self.conn.execute(
                """INSERT INTO ticket_panels
                   (guild_id, title, content, color, category_id, button_label,
                    button_emoji, welcome_message, mention_on_open)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (guild_id, data['title'], data['content'], data['color'],
                 data['category_id'], data['button_label'], data.get('button_emoji'),
                 data.get('welcome_message'),
                 json.dumps(data.get('mention_on_open', []))))
            await self._commit_if_not_in_tx()
            return cur.lastrowid

    async def get_panel(self, panel_id: int, guild_id: Optional[int] = None) -> Optional[dict]:
        async with self._lock:
            if not self.conn:
                return None
            if guild_id is not None:
                query = "SELECT * FROM ticket_panels WHERE panel_id=? AND guild_id=?"
                params = (panel_id, guild_id)
            else:
                query = "SELECT * FROM ticket_panels WHERE panel_id=?"
                params = (panel_id,)
            async with self.conn.execute(query, params) as cur:
                row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d['mention_on_open'] = json.loads(d['mention_on_open'] or '[]')
            return d

    async def list_panels(self, guild_id: int) -> list[dict]:
        async with self._lock:
            if not self.conn:
                return []
            async with self.conn.execute(
                "SELECT * FROM ticket_panels WHERE guild_id=?", (guild_id,)) as cur:
                rows = [dict(r) for r in await cur.fetchall()]
            for d in rows:
                d['mention_on_open'] = json.loads(d['mention_on_open'] or '[]')
            return rows

    async def set_panel_message(self, panel_id: int, channel_id: int, message_id: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "UPDATE ticket_panels SET channel_id=?, message_id=? WHERE panel_id=?",
                (channel_id, message_id, panel_id))
            await self._commit_if_not_in_tx()

    async def update_panel(self, panel_id: int, **kwargs) -> bool:
        async with self._lock:
            if not self.conn:
                return False
            valid = ['title', 'content', 'button_label', 'welcome_message', 'color']
            updates = {k: v for k, v in kwargs.items() if k in valid and v is not None}
            if not updates:
                return False
            clause = ", ".join(f"{k}=?" for k in updates)
            await self.conn.execute(
                f"UPDATE ticket_panels SET {clause} WHERE panel_id=?",
                list(updates.values()) + [panel_id])
            await self._commit_if_not_in_tx()
            return True

    async def delete_panel(self, panel_id: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "DELETE FROM ticket_panels WHERE panel_id=?", (panel_id,))
            await self._commit_if_not_in_tx()


    # ---------- tickets ----------
    async def create_ticket(self, guild_id: int, number: int, channel_id: int,
                            owner_id: int, panel_id: Optional[int]) -> int:
        async with self._lock:
            if not self.conn:
                return 0
            cur = await self.conn.execute(
                """INSERT INTO tickets (guild_id, number, channel_id, owner_id, panel_id)
                   VALUES (?,?,?,?,?)""",
                (guild_id, number, channel_id, owner_id, panel_id))
            await self._commit_if_not_in_tx()
            return cur.lastrowid

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[dict]:
        async with self._lock:
            if not self.conn:
                return None
            async with self.conn.execute(
                "SELECT * FROM tickets WHERE channel_id=?", (channel_id,)) as cur:
                row = await cur.fetchone()
            return dict(row) if row else None

    async def count_open_tickets(self, guild_id: int, owner_id: int) -> int:
        async with self._lock:
            if not self.conn:
                return 0
            async with self.conn.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id=? AND owner_id=? AND open=1",
                (guild_id, owner_id)) as cur:
                row = await cur.fetchone()
            return row[0] if row else 0

    async def set_claim(self, channel_id: int, staff_id: Optional[int]):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "UPDATE tickets SET claimed_by=? WHERE channel_id=?", (staff_id, channel_id))
            await self._commit_if_not_in_tx()

    async def close_ticket_db(self, channel_id: int, reason: Optional[str]) -> bool:
        async with self._lock:
            if not self.conn:
                return False
            cur = await self.conn.execute(
                "UPDATE tickets SET open=0, close_time=?, close_reason=? WHERE channel_id=? AND open=1",
                (datetime.now(timezone.utc).isoformat(), reason, channel_id))
            await self._commit_if_not_in_tx()
            return cur.rowcount > 0

    async def touch_ticket(self, channel_id: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "UPDATE tickets SET last_message_time=? WHERE channel_id=? AND open=1",
                (datetime.now(timezone.utc).isoformat(), channel_id))
            await self._commit_if_not_in_tx()

    async def exclude_autoclose(self, channel_id: int):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "UPDATE tickets SET excluded_autoclose=1 WHERE channel_id=?", (channel_id,))
            await self._commit_if_not_in_tx()

    async def get_inactive_tickets(self) -> list[dict]:
        """Trả về ticket mở, không bị loại trừ, có last_message_time cũ hơn autoclose_hours."""
        async with self._lock:
            if not self.conn:
                return []
            async with self.conn.execute(
                """SELECT t.* FROM tickets t
                   JOIN ticket_settings s ON s.guild_id = t.guild_id
                   WHERE t.open=1 AND t.excluded_autoclose=0
                     AND s.autoclose_hours > 0
                     AND julianday('now') - julianday(t.last_message_time) > (s.autoclose_hours / 24.0)""") as cur:
                return [dict(r) for r in await cur.fetchall()]

    # ---------- tags ----------
    async def add_tag(self, guild_id: int, tag_id: str, content: str):
        async with self._lock:
            if not self.conn:
                return
            await self.conn.execute(
                "INSERT OR REPLACE INTO ticket_tags (guild_id, tag_id, content) VALUES (?,?,?)",
                (guild_id, tag_id.lower(), content))
            await self._commit_if_not_in_tx()

    async def delete_tag(self, guild_id: int, tag_id: str) -> bool:
        async with self._lock:
            if not self.conn:
                return False
            cur = await self.conn.execute(
                "DELETE FROM ticket_tags WHERE guild_id=? AND tag_id=?",
                (guild_id, tag_id.lower()))
            await self._commit_if_not_in_tx()
            return cur.rowcount > 0

    async def get_tag(self, guild_id: int, tag_id: str) -> Optional[str]:
        async with self._lock:
            if not self.conn:
                return None
            async with self.conn.execute(
                "SELECT content FROM ticket_tags WHERE guild_id=? AND tag_id=?",
                (guild_id, tag_id.lower())) as cur:
                row = await cur.fetchone()
            return row[0] if row else None

    async def list_tags(self, guild_id: int) -> list[str]:
        async with self._lock:
            if not self.conn:
                return []
            async with self.conn.execute(
                "SELECT tag_id FROM ticket_tags WHERE guild_id=?", (guild_id,)) as cur:
                return [r[0] for r in await cur.fetchall()]
