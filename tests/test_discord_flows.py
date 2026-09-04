from __future__ import annotations

import asyncio
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from sqlalchemy.exc import SQLAlchemyError

from blastbot.modules.automation.cog import AutomationCog
from blastbot.modules.moderation.cog import ModerationCog
from blastbot.modules.roles.ui import RoleMenuSelect, RoleMenuSetupSelect


def http_error(status: int = 500) -> discord.HTTPException:
    response = SimpleNamespace(status=status, reason="test", headers={})
    error_type = discord.Forbidden if status == 403 else discord.HTTPException
    return error_type(response, "injected failure")


def interaction(guild: object) -> SimpleNamespace:
    return SimpleNamespace(
        guild=guild,
        guild_id=getattr(guild, "id", None),
        channel_id=10,
        user=SimpleNamespace(id=99, mention="<@99>"),
        response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(),
    )


class ModerationFlowTests(unittest.IsolatedAsyncioTestCase):
    def make_cog(self, moderation: object, repository: object | None = None) -> ModerationCog:
        cog = object.__new__(ModerationCog)
        cog.bot = SimpleNamespace(
            app=SimpleNamespace(
                moderation=moderation,
                moderation_repo=repository
                or SimpleNamespace(
                    remove_temp_role=AsyncMock(),
                    expired_temp_roles=AsyncMock(),
                    get_temp_role=AsyncMock(return_value=None),
                ),
            )
        )
        cog._validate_target = AsyncMock(return_value=True)  # type: ignore[method-assign]
        cog._confirm = AsyncMock(return_value=True)  # type: ignore[method-assign]
        cog._emit_log = AsyncMock()  # type: ignore[method-assign]
        return cog

    async def test_softban_ban_failure_does_not_audit(self) -> None:
        guild = SimpleNamespace(id=1, ban=AsyncMock(side_effect=http_error()), unban=AsyncMock())
        moderation = SimpleNamespace(record_action=AsyncMock())
        cog = self.make_cog(moderation)
        call = interaction(guild)
        member = SimpleNamespace(id=2, mention="<@2>")
        with self.assertRaises(discord.HTTPException):
            await ModerationCog.softban.callback(cog, call, member, None, 1)
        guild.unban.assert_not_awaited()
        moderation.record_action.assert_not_awaited()

    async def test_softban_success(self) -> None:
        guild = SimpleNamespace(id=1, ban=AsyncMock(), unban=AsyncMock())
        moderation = SimpleNamespace(record_action=AsyncMock())
        cog = self.make_cog(moderation)
        call = interaction(guild)
        member = SimpleNamespace(id=2, mention="<@2>")
        await ModerationCog.softban.callback(cog, call, member, "reason", 1)
        moderation.record_action.assert_awaited_once()
        self.assertEqual(moderation.record_action.await_args.args[0], "SOFTBAN")
        self.assertEqual(call.edit_original_response.await_args.kwargs["embed"].title, "Đã softban")

    async def test_softban_transient_unban_retry(self) -> None:
        guild = SimpleNamespace(
            id=1,
            ban=AsyncMock(),
            unban=AsyncMock(side_effect=[http_error(), None]),
        )
        moderation = SimpleNamespace(record_action=AsyncMock())
        cog = self.make_cog(moderation)
        call = interaction(guild)
        member = SimpleNamespace(id=2, mention="<@2>")
        with patch("blastbot.modules.moderation.cog.asyncio.sleep", new=AsyncMock()) as sleep:
            await ModerationCog.softban.callback(cog, call, member, None, 1)
        self.assertEqual(guild.unban.await_count, 2)
        sleep.assert_awaited_once()
        self.assertEqual(moderation.record_action.await_args.args[0], "SOFTBAN")

    async def test_softban_unban_failure_reports_still_banned(self) -> None:
        guild = SimpleNamespace(
            id=1,
            ban=AsyncMock(),
            unban=AsyncMock(side_effect=[http_error(), http_error(), http_error()]),
        )
        moderation = SimpleNamespace(record_action=AsyncMock())
        cog = self.make_cog(moderation)
        call = interaction(guild)
        member = SimpleNamespace(id=2, mention="<@2>")
        with patch("blastbot.modules.moderation.cog.asyncio.sleep", new=AsyncMock()):
            await ModerationCog.softban.callback(cog, call, member, None, 1)
        self.assertEqual(moderation.record_action.await_args.args[0], "SOFTBAN_PARTIAL")
        card = call.edit_original_response.await_args.kwargs["embed"]
        self.assertIn("vẫn đang bị ban", card.description)

    async def test_discord_success_audit_failure_reports_partial_state(self) -> None:
        member = SimpleNamespace(id=2, mention="<@2>", kick=AsyncMock())
        guild = SimpleNamespace(id=1)
        moderation = SimpleNamespace(record_action=AsyncMock(side_effect=SQLAlchemyError("db")))
        cog = self.make_cog(moderation)
        call = interaction(guild)
        await ModerationCog.kick.callback(cog, call, member, None)
        member.kick.assert_awaited_once()
        card = call.edit_original_response.await_args.kwargs["embed"]
        self.assertIn("audit lỗi", card.title)

    async def test_log_channel_failure_does_not_change_successful_action_or_audit(self) -> None:
        channel = SimpleNamespace(send=AsyncMock(side_effect=http_error()))
        guild = SimpleNamespace(id=1, get_channel=lambda _: channel)
        repository = SimpleNamespace(get_log_channel_id=AsyncMock(return_value=10))
        moderation = SimpleNamespace(record_action=AsyncMock())
        cog = self.make_cog(moderation, repository)
        del cog._emit_log
        call = interaction(guild)
        member = SimpleNamespace(id=2, mention="<@2>", kick=AsyncMock())
        with patch("blastbot.modules.moderation.cog.discord.TextChannel", object):
            await ModerationCog.kick.callback(cog, call, member, None)
        moderation.record_action.assert_awaited_once()
        channel.send.assert_awaited_once()
        self.assertEqual(call.edit_original_response.await_args.kwargs["embed"].title, "Đã kick")

    async def test_temprole_db_failure_never_adds_role(self) -> None:
        moderation = SimpleNamespace(
            add_temp_role=AsyncMock(side_effect=SQLAlchemyError("db")),
            record_action=AsyncMock(),
        )
        repository = SimpleNamespace(
            remove_temp_role=AsyncMock(), get_temp_role=AsyncMock(return_value=None)
        )
        cog = self.make_cog(moderation, repository)
        guild = SimpleNamespace(id=1)
        call = interaction(guild)
        member = SimpleNamespace(id=2, mention="<@2>", add_roles=AsyncMock())
        role = SimpleNamespace(id=3, name="Role", mention="<@&3>")
        with (
            patch("blastbot.modules.moderation.cog.discord.Member", object),
            patch("blastbot.modules.moderation.cog.validate_member_manage", return_value=None),
            patch("blastbot.modules.moderation.cog.validate_role_manage", return_value=None),
            self.assertRaises(SQLAlchemyError),
        ):
            await ModerationCog.temprole.callback(cog, call, member, role, 5, None)
        member.add_roles.assert_not_awaited()

    async def test_temprole_discord_failure_compensates_intent(self) -> None:
        expiry = datetime.now(UTC)
        moderation = SimpleNamespace(
            add_temp_role=AsyncMock(return_value=expiry), record_action=AsyncMock()
        )
        repository = SimpleNamespace(
            remove_temp_role=AsyncMock(), get_temp_role=AsyncMock(return_value=None)
        )
        cog = self.make_cog(moderation, repository)
        guild = SimpleNamespace(id=1)
        call = interaction(guild)
        member = SimpleNamespace(
            id=2, mention="<@2>", add_roles=AsyncMock(side_effect=http_error())
        )
        role = SimpleNamespace(id=3, name="Role", mention="<@&3>")
        with (
            patch("blastbot.modules.moderation.cog.discord.Member", object),
            patch("blastbot.modules.moderation.cog.validate_member_manage", return_value=None),
            patch("blastbot.modules.moderation.cog.validate_role_manage", return_value=None),
            self.assertRaises(discord.HTTPException),
        ):
            await ModerationCog.temprole.callback(cog, call, member, role, 5, None)
        repository.remove_temp_role.assert_awaited_once_with(1, 2, 3)

    async def test_temprole_compensation_failure_preserves_primary_error(self) -> None:
        moderation = SimpleNamespace(
            add_temp_role=AsyncMock(return_value=datetime.now(UTC)),
            record_action=AsyncMock(),
        )
        repository = SimpleNamespace(
            get_temp_role=AsyncMock(return_value=None),
            remove_temp_role=AsyncMock(side_effect=SQLAlchemyError("cleanup")),
        )
        cog = self.make_cog(moderation, repository)
        call = interaction(SimpleNamespace(id=1))
        primary = http_error()
        member = SimpleNamespace(
            id=2, mention="<@2>", add_roles=AsyncMock(side_effect=primary)
        )
        role = SimpleNamespace(id=3, mention="<@&3>")
        with (
            patch("blastbot.modules.moderation.cog.discord.Member", object),
            patch("blastbot.modules.moderation.cog.validate_member_manage", return_value=None),
            patch("blastbot.modules.moderation.cog.validate_role_manage", return_value=None),
            self.assertRaises(discord.HTTPException) as raised,
        ):
            await ModerationCog.temprole.callback(cog, call, member, role, 5, None)
        self.assertIs(raised.exception, primary)

    async def test_temprole_success_keeps_durable_cleanup(self) -> None:
        expiry = datetime.now(UTC)
        moderation = SimpleNamespace(
            add_temp_role=AsyncMock(return_value=expiry), record_action=AsyncMock()
        )
        repository = SimpleNamespace(
            get_temp_role=AsyncMock(return_value=None), remove_temp_role=AsyncMock()
        )
        cog = self.make_cog(moderation, repository)
        call = interaction(SimpleNamespace(id=1))
        member = SimpleNamespace(id=2, mention="<@2>", add_roles=AsyncMock())
        role = SimpleNamespace(id=3, mention="<@&3>")
        with (
            patch("blastbot.modules.moderation.cog.discord.Member", object),
            patch("blastbot.modules.moderation.cog.validate_member_manage", return_value=None),
            patch("blastbot.modules.moderation.cog.validate_role_manage", return_value=None),
        ):
            await ModerationCog.temprole.callback(cog, call, member, role, 5, None)
        moderation.add_temp_role.assert_awaited_once()
        member.add_roles.assert_awaited_once()
        repository.remove_temp_role.assert_not_awaited()

    async def test_concurrent_temprole_grants_are_serialized_per_target(self) -> None:
        active = 0
        max_active = 0

        async def persist(**_kwargs: object) -> datetime:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0)
            active -= 1
            return datetime.now(UTC)

        moderation = SimpleNamespace(add_temp_role=persist)
        repository = SimpleNamespace(get_temp_role=AsyncMock(return_value=None))
        cog = self.make_cog(moderation, repository)
        call = interaction(SimpleNamespace(id=1))
        member = SimpleNamespace(id=2, add_roles=AsyncMock())
        role = SimpleNamespace(id=3)
        await asyncio.gather(
            cog._grant_temp_role(call, member, role, 5, None),
            cog._grant_temp_role(call, member, role, 5, None),
        )
        self.assertEqual(max_active, 1)

    async def test_temprole_cleanup_retries_transient_failures(self) -> None:
        expired = datetime(2020, 1, 1)
        rows = [
            SimpleNamespace(guild_id=1, user_id=1, role_id=1, expires_at=expired),
            SimpleNamespace(guild_id=2, user_id=2, role_id=2, expires_at=expired),
            SimpleNamespace(guild_id=3, user_id=3, role_id=3, expires_at=expired),
        ]
        repository = SimpleNamespace(
            expired_temp_roles=AsyncMock(return_value=rows),
            get_temp_role=AsyncMock(side_effect=rows),
            remove_temp_role=AsyncMock(),
        )
        forbidden_member = SimpleNamespace(
            id=1, remove_roles=AsyncMock(side_effect=http_error(403))
        )
        failed_member = SimpleNamespace(id=2, remove_roles=AsyncMock(side_effect=http_error()))
        success_member = SimpleNamespace(id=3, remove_roles=AsyncMock())
        guilds = {
            1: SimpleNamespace(
                id=1, get_member=lambda _: forbidden_member, get_role=lambda _: object()
            ),
            2: SimpleNamespace(
                id=2, get_member=lambda _: failed_member, get_role=lambda _: object()
            ),
            3: SimpleNamespace(
                id=3, get_member=lambda _: success_member, get_role=lambda _: object()
            ),
        }
        cog = self.make_cog(SimpleNamespace(), repository)
        cog.bot.get_guild = guilds.get
        await cog._cleanup_temp_roles(datetime.now(UTC))
        repository.remove_temp_role.assert_awaited_once_with(3, 3, 3)

    async def test_temprole_cleanup_removes_missing_resources(self) -> None:
        expired = datetime(2020, 1, 1)
        rows = [
            SimpleNamespace(guild_id=1, user_id=1, role_id=1, expires_at=expired),
            SimpleNamespace(guild_id=2, user_id=2, role_id=2, expires_at=expired),
            SimpleNamespace(guild_id=3, user_id=3, role_id=3, expires_at=expired),
        ]
        repository = SimpleNamespace(
            expired_temp_roles=AsyncMock(return_value=rows),
            get_temp_role=AsyncMock(side_effect=rows),
            remove_temp_role=AsyncMock(),
        )
        guilds = {
            2: SimpleNamespace(id=2, get_member=lambda _: None, get_role=lambda _: object()),
            3: SimpleNamespace(id=3, get_member=lambda _: object(), get_role=lambda _: None),
        }
        cog = self.make_cog(SimpleNamespace(), repository)
        cog.bot.get_guild = guilds.get
        await cog._cleanup_temp_roles(datetime.now(UTC))
        self.assertEqual(repository.remove_temp_role.await_count, 3)

    async def test_temprole_cleanup_skips_intent_extended_after_query(self) -> None:
        stale = SimpleNamespace(
            guild_id=1, user_id=1, role_id=1, expires_at=datetime(2020, 1, 1)
        )
        extended = SimpleNamespace(
            guild_id=1, user_id=1, role_id=1, expires_at=datetime(2099, 1, 1)
        )
        repository = SimpleNamespace(
            expired_temp_roles=AsyncMock(return_value=[stale]),
            get_temp_role=AsyncMock(return_value=extended),
            remove_temp_role=AsyncMock(),
        )
        cog = self.make_cog(SimpleNamespace(), repository)
        cog.bot.get_guild = unittest.mock.Mock()
        await cog._cleanup_temp_roles(datetime.now(UTC))
        cog.bot.get_guild.assert_not_called()
        repository.remove_temp_role.assert_not_awaited()


class DeliveryAndRoleMenuTests(unittest.IsolatedAsyncioTestCase):
    async def test_rolemenu_single_mode_uses_one_atomic_role_edit(self) -> None:
        class FakeRole:
            def __init__(self, role_id: int) -> None:
                self.id = role_id
                self.managed = False
                self.mention = f"<@&{role_id}>"

            def __ge__(self, _other: object) -> bool:
                return False

        class FakeMember:
            def __init__(self) -> None:
                self.id = 5
                self.roles = [FakeRole(0)]
                self.edits: list[list[int]] = []

            async def edit(self, *, roles: list[FakeRole], reason: str) -> None:
                await asyncio.sleep(0)
                self.edits.append([role.id for role in roles])
                self.roles = roles

        choices = {1: FakeRole(1), 2: FakeRole(2)}
        member = FakeMember()
        guild = SimpleNamespace(
            id=1,
            me=SimpleNamespace(top_role=object()),
            get_role=choices.get,
        )
        service = SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(
                    guild_id=1, channel_id=10, role_ids=(1, 2), mode="single"
                )
            )
        )
        bot = SimpleNamespace(app=SimpleNamespace(role_menus=service))
        selects = [RoleMenuSelect(bot, mode="single") for _ in choices]
        for select, value in zip(selects, ("1", "2"), strict=True):
            select._values = [value]
        calls = [
            SimpleNamespace(
                message=SimpleNamespace(id=100),
                guild=guild,
                channel_id=10,
                user=member,
                response=SimpleNamespace(send_message=AsyncMock()),
            )
            for _ in selects
        ]
        with patch("blastbot.modules.roles.ui.discord.Member", object):
            await asyncio.gather(
                *(select.callback(call) for select, call in zip(selects, calls, strict=True))
            )
        self.assertEqual(len(member.edits), 2)
        self.assertTrue(all(len(set(edit) & {1, 2}) == 1 for edit in member.edits))

    async def test_automsg_send_success_mark_sent_failure_is_at_least_once(self) -> None:
        row = SimpleNamespace(
            id=1,
            guild_id=1,
            channel_id=10,
            use_embed=False,
            content="hello",
        )
        repository = SimpleNamespace(
            due_auto_messages=AsyncMock(return_value=[row]),
            mark_sent=AsyncMock(side_effect=SQLAlchemyError("db")),
            toggle_auto_message=AsyncMock(),
        )
        channel = SimpleNamespace(send=AsyncMock())
        cog = object.__new__(AutomationCog)
        cog.bot = SimpleNamespace(
            app=SimpleNamespace(automation_repo=repository),
            get_guild=lambda _: SimpleNamespace(get_channel=lambda _: channel),
        )
        with patch("blastbot.modules.automation.cog.discord.TextChannel", object):
            await cog._send_due_auto_messages(datetime.now(UTC))
            await cog._send_due_auto_messages(datetime.now(UTC))
        self.assertEqual(channel.send.await_count, 2)

    async def test_rolemenu_db_failure_deletes_message(self) -> None:
        message = SimpleNamespace(id=5, delete=AsyncMock(), jump_url="url")
        channel = SimpleNamespace(id=10, send=AsyncMock(return_value=message))
        bot = SimpleNamespace(
            app=SimpleNamespace(
                role_menus=SimpleNamespace(create=AsyncMock(side_effect=SQLAlchemyError("db")))
            )
        )
        select = RoleMenuSetupSelect(
            bot, channel=channel, title="Title", description="Description", mode="toggle"
        )
        role = SimpleNamespace(id=3, name="Role", mention="<@&3>")
        select._values = [role]
        call = interaction(SimpleNamespace(id=1, me=object()))
        with (
            patch("blastbot.modules.roles.ui.discord.Member", object),
            patch("blastbot.modules.roles.ui.discord.Role", object),
            patch("blastbot.modules.roles.ui.validate_role_manage", return_value=None),
            self.assertRaises(SQLAlchemyError),
        ):
            await select.callback(call)
        message.delete.assert_awaited_once()

    async def test_rolemenu_send_failure_does_not_persist(self) -> None:
        channel = SimpleNamespace(id=10, send=AsyncMock(side_effect=http_error()))
        service = SimpleNamespace(create=AsyncMock())
        bot = SimpleNamespace(app=SimpleNamespace(role_menus=service))
        select = RoleMenuSetupSelect(
            bot, channel=channel, title="Title", description="Description", mode="toggle"
        )
        select._values = [SimpleNamespace(id=3, name="Role", mention="<@&3>")]
        call = interaction(SimpleNamespace(id=1, me=object()))
        with (
            patch("blastbot.modules.roles.ui.discord.Member", object),
            patch("blastbot.modules.roles.ui.discord.Role", object),
            patch("blastbot.modules.roles.ui.validate_role_manage", return_value=None),
            self.assertRaises(discord.HTTPException),
        ):
            await select.callback(call)
        service.create.assert_not_awaited()

    async def test_rolemenu_delete_compensation_failure_preserves_db_error(self) -> None:
        original = SQLAlchemyError("db")
        message = SimpleNamespace(
            id=5, delete=AsyncMock(side_effect=http_error()), jump_url="url"
        )
        channel = SimpleNamespace(id=10, send=AsyncMock(return_value=message))
        service = SimpleNamespace(create=AsyncMock(side_effect=original))
        select = RoleMenuSetupSelect(
            SimpleNamespace(app=SimpleNamespace(role_menus=service)),
            channel=channel,
            title="Title",
            description="Description",
            mode="toggle",
        )
        select._values = [SimpleNamespace(id=3, name="Role", mention="<@&3>")]
        call = interaction(SimpleNamespace(id=1, me=object()))
        with (
            patch("blastbot.modules.roles.ui.discord.Member", object),
            patch("blastbot.modules.roles.ui.discord.Role", object),
            patch("blastbot.modules.roles.ui.validate_role_manage", return_value=None),
            self.assertRaises(SQLAlchemyError) as raised,
        ):
            await select.callback(call)
        self.assertIs(raised.exception, original)

    async def test_rolemenu_success_persists_and_keeps_message(self) -> None:
        message = SimpleNamespace(id=5, delete=AsyncMock(), jump_url="url")
        channel = SimpleNamespace(id=10, send=AsyncMock(return_value=message))
        service = SimpleNamespace(create=AsyncMock())
        select = RoleMenuSetupSelect(
            SimpleNamespace(app=SimpleNamespace(role_menus=service)),
            channel=channel,
            title="Title",
            description="Description",
            mode="toggle",
        )
        select._values = [SimpleNamespace(id=3, name="Role", mention="<@&3>")]
        call = interaction(SimpleNamespace(id=1, me=object()))
        with (
            patch("blastbot.modules.roles.ui.discord.Member", object),
            patch("blastbot.modules.roles.ui.discord.Role", object),
            patch("blastbot.modules.roles.ui.validate_role_manage", return_value=None),
        ):
            await select.callback(call)
        service.create.assert_awaited_once()
        message.delete.assert_not_awaited()
        call.response.edit_message.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
