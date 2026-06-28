# BlastBot — Development Standards

This document is the **single source of truth** for all conventions when developing
BlastBot. It is **mandatory** for every new feature — whether written by a human or an AI.
The goal: new code must always stay consistent with the existing architecture (tickets,
moderation, automation), survive bot restarts, and remain safe when Discord data
(channels/messages/roles) is deleted directly by an admin.

**Foundational principle:** *A feature is not complete until it has survived one bot restart
and one admin manually deleting the channel/message/role it depends on.*

When this document conflicts with older code, **this document wins** (and the old code
should be gradually refactored to match).

---

## Table of Contents

1. [Core Philosophy](#1-core-philosophy)
2. [Code Structure & Organization](#2-code-structure--organization)
3. [Naming Conventions](#3-naming-conventions)
4. [Cog Standards](#4-cog-standards)
5. [Slash Command Standards](#5-slash-command-standards)
6. [Database Standards](#6-database-standards)
7. [Long-Lived ID Storage (channel / message / role) — MOST CRITICAL](#7-long-lived-id-storage-channel--message--role--most-critical)
8. [Background Tasks & Scheduling](#8-background-tasks--scheduling)
9. [Input Validation & Error Handling](#9-input-validation--error-handling)
10. [Permissions](#10-permissions)
11. [User-Facing Responses (Embeds & UX)](#11-user-facing-responses-embeds--ux)
12. [UI Components & Persistent Views](#12-ui-components--persistent-views)
13. [Logging](#13-logging)
14. [Language & i18n](#14-language--i18n)
15. [Testing](#15-testing)
16. [Typing & Code Quality](#16-typing--code-quality)
17. [Pre-Merge Checklist](#17-pre-merge-checklist)
18. [Anti-Patterns — Strictly Avoid](#18-anti-patterns--strictly-avoid)

---

## 1. Core Philosophy

| Principle | Explanation |
|-----------|-------------|
| **Slash-first** | Prefer `app_commands` (slash commands). Prefix commands exist only for the legacy error handler. |
| **Fully async** | All I/O (DB, Discord API) must be `await`ed. Never block the event loop. |
| **Fail-safe** | Code must survive when the DB is not ready, a channel is deleted, or the bot lacks permissions. Always check for `None`. |
| **Restart-resilient** | A feature is incomplete until it survives a restart and a manual deletion of its dependent Discord objects. |
| **DRY via mixins/base** | Shared logic lives in `BaseModerationCog`, DB mixins, or `helpers.py`. No copy-paste. |
| **Layer separation** | Cogs handle interactions → Database handles data → Embeds/Views handle presentation. Never mix them. |
| **Auto-discovery** | New cogs are loaded automatically by `_discover_extensions()`. Never edit `main.py` to register a cog. |
| **Persistence before timing** | Never rely on in-memory `asyncio.sleep` to schedule future work. Persist the deadline to the DB and let a loop poll it. |

---

## 2. Code Structure & Organization

### 2.1 Each feature group is a package in `cogs/`

- Create a directory `cogs/<feature>/` containing an `__init__.py` with a `setup(bot)` function.
- Auto-discovery in `main.py` loads it automatically; **never** edit `main.py` to register a cog.
- The package's `__init__.py` `setup(bot)` is what auto-discovery loads, and it registers
  every cog in the package. Individual cog files conventionally also include their own
  `setup(bot)` for standalone loading, but support files (`views.py`, `helpers.py`) must not.

```python
# cogs/<feature>/__init__.py
from .main_cog import MainCog
from .daemon import DaemonCog

async def setup(bot):
    await bot.add_cog(MainCog(bot))
    await bot.add_cog(DaemonCog(bot))
```

### 2.2 Separate responsibilities by file

Follow exactly how `tickets/` and `automation/` are organized:

- A file for **user commands** (slash commands, CRUD).
- A separate **daemon** file if there is a background loop (`tasks.loop`) — do not mix the
  loop into the command file, unless the loop is tightly coupled to that cog (as in `temprole.py`).
- A **helpers** file for logic shared within the package (permission checks, rendering, etc.).
- A separate **views** file if there are UI components (buttons/selects).

### 2.3 Always access the database through `bot.db`

- Never create a new connection. Always use `db = getattr(self.bot, 'db', None)` and check for `None`.
- All of a feature's DB queries live in a dedicated **mixin** at `utils/<feature>_db.py`.

### 2.4 Directory layout

```
BlastBot/
├── main.py                  # Entry point, BlastBot class (DO NOT edit except for infra changes)
├── cogs/                    # Features, split by DOMAIN
│   ├── <domain>/
│   │   ├── __init__.py      # REQUIRED: async def setup(bot) — the auto-discovery entry point
│   │   ├── <feature>.py     # One file = one functional group (a cog)
│   │   ├── helpers.py       # (optional) domain-specific helpers — NO setup
│   │   ├── views.py         # (optional) UI components — NO setup
│   │   └── <daemon>.py      # (optional) background loop (a cog)
├── events/                  # Global listeners (error handler, etc.)
├── utils/                   # Shared infrastructure: database, embeds, views, modals...
│   └── <domain>_db.py       # DB mixin for each large domain
├── tests/                   # Unit tests, one file test_<domain>_db.py per domain
└── data/                    # SQLite (auto-created, gitignored)
```

---

## 3. Naming Conventions

| Item | Convention | Example |
|------|------------|---------|
| Domain directory | `snake_case`, plural if reasonable | `moderation/`, `tickets/` |
| Cog file | `snake_case`, by function | `auto_message.py`, `temprole.py` |
| Cog class | `PascalCase`, descriptive suffix | `BanCommand`, `TicketSetup`, `AutoMessage` |
| Logger | `BlastBot.<Domain>.<Feature>` | `BlastBot.Tickets.Views` |
| DB mixin | `<Domain>DBMixin` | `TicketDBMixin`, `AutomationDBMixin` |
| Slash command | `lowercase`, no accents/diacritics | `ban`, `automsg`, `roleinfo` |
| `custom_id` (view) | `domain:scope:action` | `ticket:panel:create`, `suggestion_upvote` |
| Constants dict | `UPPER_SNAKE` | `TICKET_CONFIG`, `COMMAND_COOLDOWNS` |

---

## 4. Cog Standards

### 4.1 Standard cog skeleton

Not every file in a `cogs/<feature>/` package is a cog. Distinguish three kinds of files:

1. **The package `__init__.py`** — this is the *only* entry point auto-discovery actually
   loads (auto-discovery scans for packages with an `__init__.py`). Its `setup(bot)` is
   responsible for registering **all** cogs in the package. **This `setup` is mandatory.**

2. **Cog files** (e.g. `panel.py`, `setup.py`, `auto_message.py`) — each contains one or more
   `commands.Cog` classes. By convention these *also* include their own `async def setup(bot)`
   so they can be loaded standalone if ever needed, but at runtime they are loaded **via the
   package `__init__.py`**, not individually by auto-discovery.

3. **Support files** (e.g. `views.py`, `helpers.py`) — these contain Views, helper functions,
   or shared logic, **not** cogs. They **must not** have a `setup` function and are simply
   imported by the cog files that use them.

```python
# cogs/<feature>/__init__.py  — REQUIRED setup, registers everything
from .main_cog import MainCog
from .daemon import DaemonCog

async def setup(bot):
    await bot.add_cog(MainCog(bot))
    await bot.add_cog(DaemonCog(bot))
```

```python
# cogs/<feature>/main_cog.py  — a cog file
"""Short description of what the cog does (Vietnamese)."""

import discord
from discord import app_commands
from discord.ext import commands
import logging

from utils.embeds import success_embed, error_embed
from utils.constants import COLORS

logger = logging.getLogger('BlastBot.<Domain>.<Feature>')


class MainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ... commands ...


async def setup(bot):              # convention for standalone loading
    await bot.add_cog(MainCog(bot))
```

### 4.2 Rules

- Moderation cogs **must** inherit from `BaseModerationCog` to share validation/logging:
  ```python
  class MyModCommand(BaseModerationCog):
      def __init__(self, bot):
          super().__init__(bot)   # NEVER forget super()
  ```
  Non-moderation features inherit from `commands.Cog`.
- A cog with a background task **must** start it in `__init__` and cancel it in `cog_unload`:
  ```python
  def __init__(self, bot):
      self.bot = bot
      self.my_loop.start()

  def cog_unload(self):
      self.my_loop.cancel()
  ```
- A cog registering a Context Menu **must** clean it up in `cog_unload` (see `ContextMenus`).
- **Always access the DB via `getattr(self.bot, 'db', None)` and check for `None`** in listeners/tasks:
  ```python
  db = getattr(self.bot, 'db', None)
  if db is None:
      return
  ```
  In normal slash commands you may use `self.bot.db` directly (the DB is connected during
  `setup_hook` before commands are synced).

---

## 5. Slash Command Standards

### 5.1 Decorator order (MANDATORY, in this exact order)

```python
@app_commands.command(name="...", description="emoji + Vietnamese description")
@app_commands.describe(param="description of each parameter")
@app_commands.autocomplete(reason=reason_autocomplete)   # if applicable
@app_commands.choices(kind=[...])                        # if applicable
@app_commands.guild_only()                               # if server-only
@app_commands.default_permissions(ban_members=True)      # command visibility gating
@require_guild_permissions(ban_members=True)             # ACTUAL permission enforcement
@app_commands.checks.cooldown(1, COMMAND_COOLDOWNS['ban'], key=lambda i: i.user.id)
async def my_command(self, interaction: discord.Interaction, ...):
    ...
```

> **Critical note:** `default_permissions` only hides the command in the UI; it does **not**
> block execution. You must use `@require_guild_permissions(...)` for real enforcement.
> Always use **both**.

### 5.2 Command body rules

1. **Check guild/member at the very top** when needed:
   ```python
   if interaction.guild is None:
       return
   ```
2. **Validate input** before doing anything else (see §9).
3. **Defer when the operation may take > 3 seconds** (heavy DB, multiple Discord API calls):
   ```python
   await interaction.response.defer(ephemeral=True)
   # ... then use interaction.followup.send(...)
   ```
4. **Respond ephemerally for admin commands** (`ephemeral=True`); respond publicly for
   community-facing commands.
5. **Each `interaction` can be `response`d to only once** — afterward use `followup` /
   `edit_original_response`.

### 5.3 Command groups

Use `app_commands.Group` for sub-command groups (see `automsg`, `ticket`, `panel`):

```python
mygroup = app_commands.Group(
    name="mygroup",
    description="Group description",
    default_permissions=discord.Permissions(manage_guild=True),
    guild_only=True)

@mygroup.command(name="add", description="...")
@require_guild_permissions(manage_guild=True)
async def add(self, interaction: discord.Interaction, ...):
    ...
```

### 5.4 Autocomplete

Place the autocomplete function **outside the class**, returning at most 25 choices:

```python
async def reason_autocomplete(interaction, current: str) -> list[app_commands.Choice[str]]:
    filtered = [r for r in REASONS if current.lower() in r.lower()]
    return [app_commands.Choice(name=r, value=r) for r in filtered[:25]]
```

---

## 6. Database Standards

### 6.1 One shared connection, serialized by a lock

All DB operations **must** be wrapped in `async with self._lock:`, and after writing must call
`await self._commit_if_not_in_tx()`. This is a rigid template — see `ticket_db.py` and
`automation_db.py`.

```python
async def create_x(self, guild_id: int, ...) -> int:
    async with self._lock:                  # 1. Always lock
        if not self.conn:                    # 2. Always check the connection
            return 0                         #    (return a safe default)
        cur = await self.conn.execute(
            "INSERT INTO ... VALUES (...)", (...))   # 3. ALWAYS parameterized query
        await self._commit_if_not_in_tx()    # 4. Commit via helper (transaction-safe)
        return cur.lastrowid or 0
```

### 6.2 Mixin pattern

- Create `utils/<feature>_db.py` with a class `XxxDBMixin`.
- Add an `init_xxx_tables(self)` method that creates tables (`CREATE TABLE IF NOT EXISTS`).
- Wire it into `Database` in `utils/database.py`:
  - Add it to the inheritance list: `class Database(TicketDBMixin, AutomationDBMixin, XxxDBMixin):`
  - Call `await self.init_xxx_tables()` inside `_initialize_tables_internal` next to the other inits.

### 6.3 Every entity must have full CRUD

You must never create data without a way to read/update/delete it. Each entity needs:

- **Create**: `create_x(...) -> int` (returns id) or `set_x(...)` (upsert).
- **Read**: `get_x(...)` (single record) and `list_x(guild_id) -> list[dict]`.
- **Update**: `update_x(...) -> bool` (whitelist fields, return `False` if nothing to update).
- **Delete**: `delete_x(...) -> bool` (return `rowcount > 0`).

CRUD at the **DB** layer must be matched by CRUD at the **user command** layer: if there is a
`/x add`, there must also be `/x list` and `/x delete`. Users must never end up in a state
where they created something they cannot view or delete.

### 6.4 Updates must whitelist fields — never format SQL from raw input

```python
async def update_x(self, x_id: int, **kwargs) -> bool:
    async with self._lock:
        if not self.conn:
            return False
        valid = ['title', 'content', 'enabled']         # hard whitelist
        updates = {k: v for k, v in kwargs.items() if k in valid and v is not None}
        if not updates:
            return False
        clause = ", ".join(f"{k}=?" for k in updates)   # column names ONLY from whitelist
        await self.conn.execute(
            f"UPDATE table SET {clause} WHERE id=?",
            list(updates.values()) + [x_id])            # values are ALWAYS ? parameters
        await self._commit_if_not_in_tx()
        return True
```

Values are **always** passed via `?`. Column names come **only** from the whitelist. No exceptions.

### 6.5 Store lists as JSON, not as concatenated-string columns

Like `mention_on_open` in tickets: `json.dumps(...)` when writing, `json.loads(... or '[]')` when reading.

### 6.6 Operations across multiple related tables → use a transaction

```python
async with self.bot.db.transaction():
    await self.bot.db.do_a(...)
    await self.bot.db.do_b(...)
# On exception → full rollback. Nested transactions are supported.
```

Nested transactions are supported (see `test_concurrent_db.py`). Use this when atomicity is
required (e.g., writing a log + updating a record, as `warn.py` does).

### 6.7 Caching

- Frequently read / rarely written data → cache with `LRUCache` (like `guild_config`).
- **Always invalidate the cache after updating**:
  ```python
  await self.conn.execute("UPDATE guilds SET ...")
  self.invalidate_cache(guild_id)
  ```

### 6.8 DB layer rules summary

| Rule | Reason |
|------|--------|
| **ALWAYS use `?` placeholders**, never f-string user values into SQL | SQL injection prevention |
| **ALWAYS `async with self._lock`** at the start of public methods | Thread/task safety with one connection |
| **ALWAYS check `if not self.conn`** and return a default | Fail-safe when the DB is closed |
| **ALWAYS call `await self._commit_if_not_in_tx()`** after writing | Compatible with nested `transaction()` |
| **Dynamic column names** (SET clause) must be whitelisted | Avoid injection via column names |
| Return `dict(row)`, never a raw `Row` out of the DB layer | Layer separation |
| Index columns frequently queried (`channel_id`, `guild_id`) | Performance |

---

## 7. Long-Lived ID Storage (channel / message / role) — MOST CRITICAL

This is the most bug-prone area. Core rule: **The DB stores only IDs (integers). Discord
objects are always re-resolved at the moment of use, and you must always assume they may have
disappeared.**

### 7.1 Store IDs, not objects

- Columns are `INTEGER`. Store `channel.id`, `message.id`, `role.id`, `guild.id`.
- Never pickle/serialize a discord.py object.

### 7.2 Resolution must check `None` AND check type

An ID may: (a) have been deleted, (b) no longer be visible to the bot, (c) have changed type
(text channel → voice channel). Always handle all three:

```python
channel = guild.get_channel(stored_id)
if not isinstance(channel, discord.TextChannel):   # this also covers None
    # orphaned record → skip or clean up, DO NOT crash
    return
```

Standard patterns already in the codebase:
- `automation/greetings.py`: `if not isinstance(channel, discord.TextChannel): return`
- `temprole.py`: `if not role or member is None: await db.remove_temp_role(...); continue`

### 7.3 Every network operation on a resolved object must be wrapped in try/except

An ID still existing does not mean the operation will succeed (missing permission, rate limit, etc.):

```python
try:
    await channel.send(...)
except discord.HTTPException as e:
    logger.warning(f"Could not send to {stored_id}: {e}")
```

### 7.4 Orphan records: auto-clean in daemons, skip gracefully at runtime

- In a **background loop**: when a guild/channel/role/member no longer exists → **delete the DB
  record** and `continue`. Standard pattern: `temprole.check_expired_roles` removes the
  temp_role when the guild/role is gone.
- At **command runtime**: if an object is orphaned → show a friendly error to the user; do not
  silently delete (unless that is the command's intent). Pattern: `TicketPanelView.create` →
  "This panel no longer exists."

### 7.5 When deleting an entity, attempt to clean up the attached Discord message — but don't require success

Standard pattern: `panel.py → panel_delete` attempts `fetch_message` then `delete`, wrapped in
`except (discord.NotFound, discord.Forbidden, discord.HTTPException): pass`, and only then
deletes the DB record. Priority order: **the DB deletion must always happen**, even if deleting
the message fails.

### 7.6 Time comparisons always use consistent UTC

- Writing: `datetime.now(timezone.utc).isoformat()` or SQLite `datetime('now')` (UTC).
- Reading/comparing: use the same basis. Avoid mixing `datetime('now')` with local `now()`.
- Pattern: `automation_db.get_due_auto_messages` and `ticket_db.get_inactive_tickets` use
  `julianday('now')` against `julianday(column)` — all in UTC.

---

## 8. Background Tasks & Scheduling

### 8.1 Persistence first, timing second

Never rely on an in-memory `asyncio.sleep` to schedule future work (it is lost on restart).
Instead: **write the expiration timestamp to the DB, then let a periodic loop poll it.**

Standard pattern: temprole writes `expires_at` to the `temp_roles` table and a loop scans
`get_expired_temp_roles()` every minute. Auto-message writes `last_sent` and a loop scans
`get_due_auto_messages()`.

### 8.2 Rigid template for a daemon cog

```python
class XDaemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.x_loop.start()

    def cog_unload(self):
        self.x_loop.cancel()          # MANDATORY: cancel the loop on unload

    @tasks.loop(minutes=CONFIG['x_check_minutes'])
    async def x_loop(self):
        db = getattr(self.bot, 'db', None)
        if db is None:
            return
        try:
            for row in await db.get_due_x():
                guild = self.bot.get_guild(row['guild_id'])
                if not guild:
                    await db.delete_x(...)   # clean up orphan
                    continue
                # ... resolve + operate, wrap each item in try/except
        except Exception as e:                # the loop MUST NOT die
            logger.error(f"Error in x_loop: {e}", exc_info=True)

    @x_loop.before_loop
    async def before(self):
        await self.bot.wait_until_ready()     # MANDATORY
```

Absolute requirements:
- `self.x_loop.start()` in `__init__`, `self.x_loop.cancel()` in `cog_unload`.
- `@x_loop.before_loop` + `await self.bot.wait_until_ready()`.
- The entire loop body wrapped in `try/except Exception` — **a single failing item must not
  kill the whole loop**.
- Each item additionally wrapped in its own `try/except` for the network operation portion.

### 8.3 Polling cadence and acceptable latency

- A loop polling by the minute means execution may be delayed by up to one poll interval.
  Document this clearly to the user where relevant (e.g., autoclose measured in hours).
- Set `min`/`max` bounds for every user-supplied time parameter (see §9).

### 8.4 If one guild has many items due at once → space out the sends

When `max_items` per guild is large, add a small `await asyncio.sleep(...)` between sends to
avoid rate limits (pattern: `clear.py` spaces out batches).

---

## 9. Input Validation & Error Handling

### 9.1 Always use the existing helpers in `utils/error_handler.py`

- `validate_number_range(value, min, max, "Name")` for numbers (durations, counts, etc.).
- `validate_string_length(text, min_len, max_len)` for strings.
- Catch `ValidationError` and return `error_embed("Lỗi", e.user_message)` ephemerally.

```python
from utils.error_handler import (
    validate_string_length, validate_number_range, ValidationError
)

try:
    content = validate_string_length(content, min_len=1, max_len=2000)
    validate_number_range(interval, MIN, MAX, "Chu kỳ (phút)")
except ValidationError as e:
    return await interaction.response.send_message(
        embed=error_embed("Lỗi", e.user_message), ephemeral=True)
```

### 9.2 Respect Discord's own limits

- Regular message content: max 2000. Embed description: max 4096 (use 4000 to be safe).
- Embed title: max 256. Channel name: ≤ 100 and slugified (`.lower().replace(" ", "-")`).
- All limit constants live in `utils/constants.py` (see `AUTOMATION_CONFIG`, `TICKET_CONFIG`);
  **never** hardcode them scattered across cogs.

### 9.3 Block guild/None states early

Every guild-only command: `if interaction.guild is None: return` at the top of the function,
and use `@app_commands.guild_only()`.

### 9.4 Exception hierarchy (use the existing classes)

```
BotError                  # base, has message (for logs) + user_message (for display)
├── DatabaseError
├── ValidationError
└── BotPermissionError
```

When raising an error meant to be displayed, **always provide a Vietnamese `user_message`**:
```python
raise ValidationError("interval out of range", "❌ Chu kỳ phải từ 5 đến 10080 phút!")
```

### 9.5 try/except placement

- Moderation commands: wrap in `try/except`, use `self.safe_error_response(...)` (safe whether
  or not the interaction was already deferred).
- Background tasks: wrap the entire loop body in `try/except Exception` + `logger.error(..., exc_info=True)`;
  **never let a task die silently**.
- Discord API: catch specifics — `discord.Forbidden`, `discord.NotFound`, `discord.HTTPException` —
  not a bare `Exception` when avoidable.
- Slash command errors automatically pass through `handle_command_error` (wired in `main.py`).
  **Do not** manually handle the usual cooldown/permission errors — they are already mapped to
  Vietnamese messages.

---

## 10. Permissions

| Layer | Tool | Purpose |
|-------|------|---------|
| UI gating | `@app_commands.default_permissions(...)` | Hide the command from users without the permission |
| Enforcement | `@require_guild_permissions(...)` | **Actually block execution** |
| Hierarchy | `await self.validate_hierarchy(interaction, target)` | Disallow acting on a higher role |
| Valid target | `await self.validate_target(interaction, target)` | Block self / bot / owner targeting |
| Ticket staff | `await is_ticket_staff(bot, member)` | Internal ticket authorization |

Rules:
- Admin commands: use **both** `@app_commands.default_permissions(...)` (UI gating) **and**
  `@require_guild_permissions(...)` (execution enforcement). Two layers, never drop one.
- `require_guild_permissions` lives in `cogs/moderation/base.py` — import it, do not rewrite it.
- Actions on another member (kick/ban/role/etc.): must go through `BaseModerationCog`'s
  `validate_hierarchy` and `validate_target`.
- Moderation features inherit `BaseModerationCog`. Other features inherit `commands.Cog`.

---

## 11. User-Facing Responses (Embeds & UX)

- Use the helpers: `success_embed`, `error_embed`, `warning_embed`, `info_embed`, `create_embed`
  from `utils/embeds.py`. Do not hand-build `discord.Embed` for standard notifications.
- Config/admin responses: `ephemeral=True`.
- Colors come from `COLORS` in constants; never hardcode hex values. Emojis come from `EMOJIS`.
- Destructive actions (delete, ban, close ticket): a confirmation step is mandatory
  (`ConfirmView` or `ConfirmCloseView`) before execution.
- User-facing text: Vietnamese, with leading emojis (✅ ❌ ⚠️), `**bold**` for important values,
  and `` `code` `` for IDs/technical values.
- Mention via `<@id>` / `<#id>` / `<@&id>` when the object may no longer be in cache.

| Situation | Helper |
|-----------|--------|
| Success | `success_embed(title, desc)` |
| Error | `error_embed(title, desc)` |
| Warning / confirmation | `warning_embed(title, desc)` |
| Info | `info_embed(title, desc)` |
| Custom | `create_embed(...)` |

---

## 12. UI Components & Persistent Views

If the feature has buttons/selects that **persist long-term** (panels, votes, close requests, etc.):

### 12.1 Persistent views must have `timeout=None` and a stable `custom_id` per button

```python
class XView(discord.ui.View):
    def __init__(self, bot=None):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="...", custom_id="x:action")   # stable custom_id
    async def action(self, interaction, button):
        bot = self.bot or interaction.client
        ...
```

### 12.2 Re-register views on startup

Add the view to `_register_persistent_views` in `main.py` (next to `TicketPanelView`,
`SuggestionVotingView`, etc.). Otherwise the buttons will be "dead" after a restart.

In persistent views, resolve bot/db safely since the view may be restored:
```python
bot = self.bot or interaction.client
db = getattr(bot, 'db', None)
```

### 12.3 Views must resolve their state from the DB, not hold state in memory

Pattern: `TicketPanelView.create` looks up the panel from the DB by `interaction.message.id`
on each click, instead of remembering the panel in the instance. This is what lets it survive a restart.

### 12.4 Transient views (single-use) use a finite timeout

Like `ConfirmView` (60s) and `HelpView` (180s). Must implement `interaction_check` so only the
invoking user can interact, and disable components in `on_timeout`.

### 12.5 Modals

- Inherit `discord.ui.Modal`, set a Vietnamese `title`.
- `TextInput` should set `max_length`, `required`, and a clear `placeholder`.
- Handle in `on_submit`, respond `ephemeral=True` to the submitter.

---

## 13. Logging

- One logger per module: `logging.getLogger('BlastBot.<Area>.<Name>')`.
- Notable successful actions: `logger.info(...)`.
- Handled/ignored errors: `logger.warning(...)`.
- Unexpected errors: `logger.error(..., exc_info=True)`.
- Development details: `logger.debug(...)`.
- No `print()`. No silently swallowing exceptions (`except: pass` is only acceptable for
  unimportant message/permission cleanup, and should log at debug level if feasible).
- Do not log tokens, sensitive content, or unnecessary PII.

---

## 14. Language & i18n

- **User-facing text: Vietnamese.** Full diacritics, friendly and polite tone.
- **Docstrings & comments:** Vietnamese (or bilingual for complex technical explanations);
  stay consistent within a file.
- **Variable, function, class, and log-key names:** English.
- **Slash command and parameter names:** English, no diacritics (Discord limitation), but the
  `description` is Vietnamese.
- If multi-language support is needed later: collect strings into `MESSAGES` (`constants.py`)
  rather than scattering them — the structure already exists for this.

---

## 15. Testing

Mandatory for every feature with a DB.

- Add `tests/test_<feature>_db.py` following the `test_ticket_db.py` / `test_automation_db.py` model.
- Use `unittest.IsolatedAsyncioTestCase` with a temporary DB (`test_*.db`), removed in `asyncTearDown`.

```python
class MyDBTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = "test_myfeature_temp.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.db = Database(self.db_path)
        await self.db.connect()

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
```

- Required tests: CRUD roundtrip (create → read → update → delete) and **time logic** if present
  (set a timestamp into the past, confirm the item appears as "due"; confirm it disappears after
  being marked).
- Pure logic (validation, placeholder rendering) should be extracted into functions so it can be
  tested without a DB.
- Also test concurrency where relevant (concurrent writes) and transaction rollback.
- Run `pytest` before merging. Do not merge with failing tests.

---

## 16. Typing & Code Quality

- **Full type hints** for every public parameter and return value:
  ```python
  async def create_panel(self, guild_id: int, **data) -> int: ...
  async def get_panel(self, panel_id: int) -> Optional[dict]: ...
  ```
- Use the correct types — `discord.Interaction`, `discord.Member`, `discord.TextChannel`, etc. —
  and use `isinstance` to narrow types where needed.
- Follow `ruff` (config in `pyproject.toml`: `E, F, I, UP, B, SIM, ASYNC`).
- Python target: **3.12+** (use `int | None`, `list[dict]`, etc.).
- Before submitting a PR:
  ```bash
  ruff check --fix .
  ruff format .
  pytest
  mypy .          # if dev deps are installed
  ```

---

## 17. Pre-Merge Checklist

Copy this checklist into the PR description and check every box before merging:

```markdown
### ✅ BlastBot Feature Checklist

- [ ] Cog lives in `cogs/<feature>/` with `__init__.py` containing `setup`; main.py NOT edited to register
- [ ] Support files (views.py, helpers.py) have NO `setup`; only cog files and the package __init__ do
- [ ] DB access via mixin `utils/<feature>_db.py`, wired into `Database` and `init_*_tables` called
- [ ] Every DB method wraps `self._lock` + `_commit_if_not_in_tx()`; updates whitelist fields
- [ ] Each entity has full CRUD at both DB and user-command layers (at minimum add/list/delete)
- [ ] All IDs stored as integers; resolution always checks `None` + type; network ops wrapped in try/except
- [ ] Orphans cleaned up in daemons, friendly error shown at runtime
- [ ] Scheduling persists a timestamp to the DB + a polling loop; NO in-memory `sleep`
- [ ] Daemon: `start`/`cancel` in `__init__`/`cog_unload`, `before_loop` + `wait_until_ready`,
      loop body wrapped in `try/except Exception`
- [ ] Time comparisons use consistent UTC
- [ ] Input validated via helpers; limits pulled from `constants.py`, not hardcoded
- [ ] Admin commands have both `default_permissions` and `require_guild_permissions`
- [ ] Moderation actions call `validate_target` + `validate_hierarchy`
- [ ] Destructive actions have a confirmation step
- [ ] User-facing text is Vietnamese using embed factories (`success_embed`/`error_embed`/...)
- [ ] Persistent views (if any): `timeout=None`, stable `custom_id`, registered in
      `_register_persistent_views`, resolve state from the DB
- [ ] Dedicated logger; no `print`, no unjustified exception swallowing
- [ ] `tests/test_<feature>_db.py` covering CRUD + time logic; `pytest` is green
- [ ] `ruff check .` and `ruff format .` run clean
- [ ] Required intents enabled in the Developer Portal (if using events like member join),
      and slash commands re-synced (set `GUILD_ID` for fast sync during dev)
- [ ] `README.md` (Commands section) and `CATEGORY_META` in `help.py` updated if a new group was added
```

---

## 18. Anti-Patterns — Strictly Avoid

| ❌ Don't | ✅ Instead |
|---------|-----------|
| `asyncio.sleep(3600)` then do work → lost on restart | Persist to DB + polling loop |
| Store a Discord object in the DB | Store only the ID |
| `guild.get_channel(id).send(...)` without a `None` check → crashes when the channel is deleted | Resolve, check `None` + type, then act |
| Format user values directly into SQL | Always use `?` placeholders |
| Create a new `aiosqlite.connect` inside a cog | Use `bot.db` |
| Create an entity with no corresponding delete command | Provide full CRUD |
| `tasks.loop` without try/except → one error kills the loop forever | Wrap the loop body in `try/except Exception` |
| Persistent view not re-registered → buttons die after restart | Register in `_register_persistent_views` |
| Mixing local and UTC time in comparisons | Use consistent UTC everywhere |
| Hardcode hex colors, numeric limits, channel IDs in cogs | Pull from `constants.py` |
| Hand-build `discord.Embed(title="Lỗi", color=0xff0000)` | Use `error_embed("Lỗi", "...")` |
| `print("debug")` | `logger.debug("...")` |
| `except: pass` swallowing errors in a task | `except Exception as e: logger.error(..., exc_info=True)` |
| Respond to the same `interaction` twice | Use `followup` / `edit_original_response` afterward |
| Reinvent length/range validation | Use `validate_string_length` / `validate_number_range` |
| Put a `setup` in a support file (views.py/helpers.py) | Only cog files and package `__init__.py` have `setup` |
| Manually register cogs in `main.py` | Let auto-discovery handle it (just provide `setup` in the package `__init__`) |

---

*This document should be updated whenever a new agreed-upon pattern emerges. Any change to the
standards must be reflected in the referenced code examples.*
