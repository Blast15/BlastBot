import asyncio
import discord
import logging

from utils.embeds import create_embed, success_embed, error_embed
from utils.constants import COLORS
from utils.transcript import generate_transcript
from .helpers import is_ticket_staff, is_blacklisted

logger = logging.getLogger('BlastBot.Tickets.Views')

_user_open_locks: dict[tuple[int, int], asyncio.Lock] = {}


def _get_user_open_lock(guild_id: int, user_id: int) -> asyncio.Lock:
    key = (guild_id, user_id)
    if key not in _user_open_locks:
        _user_open_locks[key] = asyncio.Lock()
    return _user_open_locks[key]


def build_overwrites(guild: discord.Guild, owner: discord.abc.User,
                     staff_entries: list[dict]) -> dict:
    ow = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    ow[owner] = discord.PermissionOverwrite(
        view_channel=True, send_messages=True, attach_files=True,
        embed_links=True, read_message_history=True)
    if guild.me:
        ow[guild.me] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True,
            read_message_history=True, embed_links=True, attach_files=True)
    for entry in staff_entries:
        if entry['is_role']:
            role = guild.get_role(entry['entity_id'])
            if role:
                ow[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True)
        else:
            member = guild.get_member(entry['entity_id'])
            if member:
                ow[member] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True)
    return ow


async def open_ticket(bot, interaction: discord.Interaction, panel: dict | None,
                      form_answers: dict | None = None):
    """Luồng tạo ticket dùng chung cho cả panel button và /open."""
    guild = interaction.guild
    if guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("❌ Đã xảy ra lỗi: Không xác định được guild/member.", ephemeral=True)
        return

    async with _get_user_open_lock(guild.id, interaction.user.id):
        db = bot.db
        settings = await db.get_ticket_settings(guild.id)

        if await is_blacklisted(bot, interaction.user):
            await interaction.followup.send("❌ Bạn bị chặn khỏi việc tạo ticket.", ephemeral=True)
            return

        open_count = await db.count_open_tickets(guild.id, interaction.user.id)
        if open_count >= settings['ticket_limit']:
            await interaction.followup.send(
                f"❌ Bạn đã đạt giới hạn **{settings['ticket_limit']}** ticket đang mở.",
                ephemeral=True)
            return

        category = guild.get_channel(panel['category_id']) if panel and panel.get('category_id') else None
        if panel and not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send("❌ Category ticket không hợp lệ.", ephemeral=True)
            return

        number = await db.next_ticket_number(guild.id)
        staff_entries = await db.get_staff(guild.id)
        overwrites = build_overwrites(guild, interaction.user, staff_entries)

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{number:04d}", category=category, overwrites=overwrites,
                topic=f"Ticket #{number} | Owner: {interaction.user.id}",
                reason=f"Ticket bởi {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot thiếu quyền Manage Channels.", ephemeral=True)
            return

        await db.create_ticket(guild.id, number, channel.id, interaction.user.id,
                               panel['panel_id'] if panel else None)

        welcome = (panel.get('welcome_message') if panel else None) or \
            settings.get('welcome_message') or \
            "Cảm ơn bạn đã tạo ticket! Đội ngũ hỗ trợ sẽ phản hồi sớm. Hãy mô tả vấn đề của bạn."

        embed = create_embed(title=f"🎫 Ticket #{number}", description=welcome,
                             color=COLORS['primary'])
        embed.add_field(name="Người tạo", value=interaction.user.mention, inline=True)

        if form_answers:
            for label, value in form_answers.items():
                embed.add_field(name=label, value=value[:1024] or "—", inline=False)

        mentions = ""
        if panel and panel.get('mention_on_open'):
            mentions = " ".join(f"<@&{r}>" for r in panel['mention_on_open'])

        await channel.send(content=f"{interaction.user.mention} {mentions}".strip(),
                           embed=embed, view=TicketControlView(bot))
        await interaction.followup.send(f"✅ Đã tạo ticket: {channel.mention}", ephemeral=True)
        logger.info(f"{interaction.user} mở ticket #{number} ({channel.id})")


class FormModal(discord.ui.Modal):
    """Modal động sinh từ form fields, mở ticket sau khi submit."""

    def __init__(self, bot, panel: dict, fields: list[dict], form_title: str):
        super().__init__(title=form_title[:45])
        self.bot = bot
        self.panel = panel
        self._inputs = []
        for f in fields[:5]:  # Discord giới hạn 5 field/modal
            style = (discord.TextStyle.paragraph
                     if f['style'] == 'paragraph' else discord.TextStyle.short)
            item = discord.ui.TextInput(
                label=f['label'][:45],
                placeholder=(f.get('placeholder') or "")[:100],
                required=bool(f['required']),
                style=style, max_length=1000)
            self._inputs.append((f['label'], item))
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        answers = {label: item.value for label, item in self._inputs}
        await open_ticket(self.bot, interaction, self.panel, answers)


class TicketPanelView(discord.ui.View):
    """Panel button — persistent."""

    def __init__(self, bot=None):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Tạo Ticket", style=discord.ButtonStyle.primary,
                       emoji="🎫", custom_id="ticket:panel:create")
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = self.bot or interaction.client
        db = getattr(bot, 'db', None)
        if db is None or interaction.guild is None or interaction.message is None:
            return
        # Tìm panel theo message_id
        panels = await db.list_panels(interaction.guild.id)
        panel = next((p for p in panels if p['message_id'] == interaction.message.id), None)
        if panel is None:
            await interaction.response.send_message(
                "❌ Panel này không còn tồn tại.", ephemeral=True)
            return

        if panel.get('form_id'):
            fields = await db.get_form_fields(panel['form_id'])
            if fields:
                forms = await db.list_forms(interaction.guild.id)
                title = next((f['title'] for f in forms if f['form_id'] == panel['form_id']), "Form")
                await interaction.response.send_modal(
                    FormModal(bot, panel, fields, title))
                return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await open_ticket(bot, interaction, panel)


class TicketControlView(discord.ui.View):
    """Nút trong channel ticket — persistent."""

    def __init__(self, bot=None):
        super().__init__(timeout=None)
        self.bot = bot

    async def _get(self, interaction):
        bot = self.bot or interaction.client
        db = getattr(bot, 'db', None)
        ticket = await db.get_ticket_by_channel(interaction.channel.id) if db else None
        return bot, db, ticket

    @discord.ui.button(label="Nhận xử lý", style=discord.ButtonStyle.success,
                       emoji="🙋", custom_id="ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot, db, ticket = await self._get(interaction)
        if not ticket:
            return await interaction.response.send_message("❌ Không phải ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not await is_ticket_staff(bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ staff mới claim được.", ephemeral=True)
        if ticket['claimed_by']:
            return await interaction.response.send_message(
                f"❌ Đã được <@{ticket['claimed_by']}> nhận.", ephemeral=True)
        await db.set_claim(interaction.channel.id, interaction.user.id)
        if isinstance(interaction.channel, discord.TextChannel):
            await apply_claim_perms(bot, interaction.channel, ticket, interaction.user)
        await interaction.response.send_message(
            embed=success_embed("Đã nhận xử lý",
                                f"{interaction.user.mention} phụ trách ticket này."))

    @discord.ui.button(label="Đóng", style=discord.ButtonStyle.danger,
                       emoji="🔒", custom_id="ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot, db, ticket = await self._get(interaction)
        if not ticket:
            return await interaction.response.send_message("❌ Không phải ticket.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ Lỗi người dùng.", ephemeral=True)
        if interaction.user.id != ticket['owner_id'] and not await is_ticket_staff(bot, interaction.user):
            return await interaction.response.send_message("❌ Không có quyền đóng.", ephemeral=True)
        await interaction.response.send_message(
            embed=create_embed(title="Xác nhận đóng ticket",
                               description="Channel sẽ bị xóa sau khi lưu transcript.",
                               color=COLORS['warning']),
            view=ConfirmCloseView(bot))


async def apply_claim_perms(bot, channel: discord.TextChannel, ticket: dict, claimer: discord.Member):
    """Theo claim_mode: khoá quyền gửi của staff khác."""
    settings = await bot.db.get_ticket_settings(channel.guild.id)
    mode = settings.get('claim_mode', 'reply_only')
    if mode != 'reply_only':
        return
    staff = await bot.db.get_staff(channel.guild.id)
    for entry in staff:
        if entry['is_role']:
            role = channel.guild.get_role(entry['entity_id'])
            if role:
                try:
                    await channel.set_permissions(role, view_channel=True, send_messages=False)
                except discord.HTTPException:
                    pass
    try:
        await channel.set_permissions(claimer, view_channel=True, send_messages=True)
    except discord.HTTPException:
        pass


async def perform_close(bot, channel: discord.TextChannel, closer: discord.abc.User,
                        reason: str | None):
    """Lưu transcript → log → xóa channel."""
    db = bot.db
    ticket = await db.get_ticket_by_channel(channel.id)
    if not ticket:
        return
    closed_now = await db.close_ticket_db(channel.id, reason)
    if not closed_now:
        return
    settings = await db.get_ticket_settings(channel.guild.id)
    try:
        transcript = await generate_transcript(channel)
        tc_id = settings.get('transcript_channel_id')
        log_channel = channel.guild.get_channel(tc_id) if tc_id else None
        if isinstance(log_channel, (discord.TextChannel, discord.Thread)):
            owner = channel.guild.get_member(ticket['owner_id'])
            embed = create_embed(
                title=f"🎫 Ticket #{ticket['number']} đã đóng",
                description=(f"**Người tạo:** {owner.mention if owner else ticket['owner_id']}\n"
                             f"**Đóng bởi:** {closer.mention}\n"
                             f"**Lý do:** {reason or 'Không có'}"),
                color=COLORS['info'])
            await log_channel.send(embed=embed, file=transcript)
    except discord.HTTPException as e:
        logger.error(f"Transcript lỗi: {e}")
    try:
        await channel.delete(reason=f"Ticket đóng bởi {closer}")
    except discord.HTTPException:
        pass


class ConfirmCloseView(discord.ui.View):
    def __init__(self, bot=None):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="Xác nhận đóng", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = self.bot or interaction.client
        await interaction.response.edit_message(
            embed=create_embed(title="Đang đóng...", description="Vui lòng chờ.",
                               color=COLORS['warning']), view=None)
        if isinstance(interaction.channel, discord.TextChannel):
            await perform_close(bot, interaction.channel, interaction.user, None)

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=error_embed("Đã hủy", "Ticket vẫn mở."), view=None)


class CloseRequestView(discord.ui.View):
    """Owner approve/deny close request — persistent."""

    def __init__(self, bot=None, owner_id: int | None = None, reason: str | None = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.owner_id = owner_id
        self.reason = reason

    @discord.ui.button(label="Đồng ý đóng", style=discord.ButtonStyle.success,
                       emoji="✅", custom_id="ticket:closereq:accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot = self.bot or interaction.client
        ticket = await bot.db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return
        if not isinstance(interaction.user, discord.Member):
            return
        if interaction.user.id != ticket['owner_id'] and not await is_ticket_staff(bot, interaction.user):
            return await interaction.response.send_message("❌ Chỉ chủ ticket hoặc staff mới xác nhận.", ephemeral=True)
        await interaction.response.edit_message(content="Đang đóng ticket...", view=None)
        if isinstance(interaction.channel, discord.TextChannel):
            await perform_close(bot, interaction.channel, interaction.user, self.reason)

    @discord.ui.button(label="Giữ mở", style=discord.ButtonStyle.secondary,
                       emoji="❌", custom_id="ticket:closereq:deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            return
        ticket = await (self.bot or interaction.client).db.get_ticket_by_channel(interaction.channel.id)
        if ticket and interaction.user.id != ticket['owner_id']:
            return await interaction.response.send_message("❌ Chỉ chủ ticket mới từ chối.", ephemeral=True)
        await interaction.response.edit_message(
            content="Yêu cầu đóng đã bị từ chối, ticket vẫn mở.", view=None)
