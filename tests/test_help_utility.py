from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
from discord import app_commands

from blastbot.core.config import Settings
from blastbot.core.errors import ValidationError
from blastbot.core.extensions import enabled_extensions
from blastbot.modules.help.cog import (
    PAGE_SIZE,
    HelpCog,
    HelpView,
    _access_label,
    category_embed,
    command_embed,
)
from blastbot.modules.moderation.cog import ModerationCog
from blastbot.modules.utility.cog import UtilityCog, build_poll


def interaction():
    return SimpleNamespace(
        user=SimpleNamespace(id=1), guild_id=10, channel_id=20,
        response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock(),
                                 defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()), original_response=AsyncMock(),
    )


def command(name="sample", description="Lệnh thử"):
    async def callback(interaction: discord.Interaction, value: str, optional: int = 3):
        pass
    return app_commands.Command(name=name, description=description, callback=callback)


class HelpTests(unittest.IsolatedAsyncioTestCase):
    async def test_navigation_pagination_timeout_and_owner(self):
        items = [command(f"cmd{i}") for i in range(19)]
        view = HelpView({"Khác": items}, owner_id=1)
        view.category = "Khác"
        view.rebuild()
        self.assertTrue(view.previous.disabled)
        self.assertFalse(view.next_page.disabled)
        selector = next(item for item in view.children if getattr(item, "kind", None) == "command")
        self.assertEqual(len(selector.options), PAGE_SIZE)
        event = interaction()
        await view.next_page.callback(event)
        self.assertEqual(view.page, 1)
        await view.next_page.callback(event)
        self.assertEqual(view.page, 2)
        self.assertTrue(view.next_page.disabled)
        view.selected = items[-1]
        await view.back.callback(event)
        self.assertIsNone(view.selected)
        await view.home.callback(event)
        self.assertIsNone(view.category)
        self.assertTrue(await view.interaction_check(event))
        event.user.id = 2
        self.assertFalse(await view.interaction_check(event))
        view.message = AsyncMock()
        await view.on_timeout()
        self.assertTrue(all(item.disabled for item in view.children))
        view.message.edit.assert_awaited_once()
        view.stop()

    async def test_select_category_and_command(self):
        item = command()
        view = HelpView({"Khác": [item]}, owner_id=1)
        select = next(
            child for child in view.children if getattr(child, "kind", None) == "category"
        )
        select._values = ["Khác"]
        await select.callback(interaction())
        select = next(child for child in view.children if getattr(child, "kind", None) == "command")
        select._values = ["sample"]
        await select.callback(interaction())
        self.assertIs(view.selected, item)
        self.assertEqual(view.embed().title, "/sample")
        view.stop()

    async def test_nested_groups_and_search(self):
        root = app_commands.Group(name="root", description="Root",
                                  default_permissions=discord.Permissions(manage_guild=True))
        child = app_commands.Group(name="child", description="Child", parent=root)
        leaf = command(description="Tạo bình chọn")
        child.add_command(leaf)
        cog = HelpCog(SimpleNamespace(tree=SimpleNamespace(get_commands=lambda: [root])))
        self.assertEqual(cog._commands(), [leaf])
        self.assertIn("manage_guild", _access_label(leaf))
        result = await cog.help_autocomplete(interaction(), "bình chọn")
        self.assertEqual(result[0].value, "root child sample")
        for query, expected in [("bình chọn", 1), ("missing", 0)]:
            event = interaction()
            await HelpCog.help.callback(cog, event, query)
            payload = event.response.send_message.call_args.kwargs
            self.assertTrue(payload["ephemeral"])
            view = payload["view"]
            self.assertEqual(sum(map(len, view.categories.values())), expected)
            view.stop()

    def test_embed_limits_and_parameter_details(self):
        items = [command(f"c{i}", "x" * 100) for i in range(50)]
        for page in range(7):
            card = category_embed("Khác", items, page)
            self.assertLessEqual(len(card.description), 4096)
            self.assertLessEqual(len(card), 6000)
        card = command_embed(items[0])
        self.assertIn("<value>", card.fields[0].value)
        self.assertIn("[optional]", card.fields[0].value)
        self.assertIn("Bắt buộc", card.fields[2].value)
        self.assertIn("Tùy chọn", card.fields[2].value)


class UtilityTests(unittest.IsolatedAsyncioTestCase):
    def test_poll_validation(self):
        poll = build_poll("Cuối tuần?", " Thứ bảy | Chủ nhật ", 24, True)
        self.assertEqual(len(poll.answers), 2)
        for question, options, hours in [
            ("", "A|B", 24), ("x" * 301, "A|B", 24), ("Q", "A", 24),
            ("Q", "A|", 24), ("Q", "A|a", 24), ("Q", "x" * 56 + "|B", 24),
            ("Q", "|".join(str(i) for i in range(11)), 24),
            ("Q", "A|B", 0), ("Q", "A|B", 169),
        ]:
            with self.subTest(options=options, hours=hours), self.assertRaises(ValidationError):
                build_poll(question, options, hours, False)

    def test_utility_can_be_disabled(self):
        settings = Settings(DISCORD_TOKEN="x" * 40, FEATURE_UTILITY=False)
        self.assertNotIn("blastbot.modules.utility.cog", enabled_extensions(settings))

    async def test_poll_sends_native_poll_after_validation(self):
        event = interaction()
        event.channel = Mock(spec=discord.TextChannel)
        event.channel.send = AsyncMock(return_value=SimpleNamespace(jump_url="https://discord.com"))
        cog = UtilityCog(SimpleNamespace())
        await UtilityCog.poll.callback(cog, event, "Q", "A|B", 1, False)
        event.response.defer.assert_awaited_once_with(ephemeral=True)
        self.assertIsInstance(event.channel.send.call_args.kwargs["poll"], discord.Poll)
        self.assertFalse(event.channel.send.call_args.kwargs["allowed_mentions"].everyone)
        event.channel.send.reset_mock()
        with self.assertRaises(ValidationError):
            await UtilityCog.poll.callback(cog, event, "Q", "A|A", 1, False)
        event.channel.send.assert_not_awaited()

    async def test_slowmode_saves_audit_and_handles_audit_failure(self):
        for audit_ok in (True, False):
            cog = object.__new__(ModerationCog)
            cog._persist_action = AsyncMock(return_value=audit_ok)
            event = interaction()
            event.channel = Mock(spec=discord.TextChannel)
            event.channel.edit = AsyncMock()
            event.channel.id, event.channel.name, event.channel.mention = 20, "general", "<#20>"
            await ModerationCog.slowmode.callback(cog, event, 0)
            event.channel.edit.assert_awaited_once_with(slowmode_delay=0, reason="Slowmode by 1")
            cog._persist_action.assert_awaited_once()
            card = event.followup.send.call_args.kwargs["embed"]
            self.assertEqual("audit lỗi" in card.title, not audit_ok)

    async def test_write_commands_require_user_and_bot_permissions(self):
        event = interaction()
        event.permissions = discord.Permissions.none()
        event.app_permissions = discord.Permissions.none()
        with self.assertRaises(app_commands.MissingPermissions):
            await ModerationCog.slowmode._check_can_run(event)
        event.permissions = discord.Permissions(manage_channels=True)
        with self.assertRaises(app_commands.BotMissingPermissions):
            await ModerationCog.slowmode._check_can_run(event)
        event.user = Mock(spec=discord.Member)
        event.user.guild_permissions = discord.Permissions.none()
        with self.assertRaises(app_commands.MissingPermissions):
            await UtilityCog.poll._check_can_run(event)
        event.user.guild_permissions = discord.Permissions(manage_messages=True)
        with self.assertRaises(app_commands.BotMissingPermissions):
            await UtilityCog.poll._check_can_run(event)

    async def test_ping_handles_disconnected_gateway(self):
        event = interaction()
        await UtilityCog.ping.callback(UtilityCog(SimpleNamespace(latency=float("nan"))), event)
        card = event.response.send_message.call_args.kwargs["embed"]
        self.assertIn("Đang kết nối", card.description)
