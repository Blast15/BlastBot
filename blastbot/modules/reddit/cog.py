from __future__ import annotations

import logging
from collections import defaultdict

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from blastbot.core.bot import BlastBot
from blastbot.database.models import RedditSubscription
from blastbot.modules.reddit.client import RedditClient, RedditPost
from blastbot.modules.reddit.service import normalize_subreddit
from blastbot.shared.embeds import error, info, success
from blastbot.shared.permissions import require_guild_permissions

logger = logging.getLogger(__name__)


def reddit_embed(post: RedditPost) -> discord.Embed:
    description = post.text
    if description and len(description) > 700:
        description = description[:697].rstrip() + "…"
    card = discord.Embed(
        title=post.title[:256],
        url=post.permalink,
        description=description,
        color=0xFF4500,
        timestamp=post.created_at,
    )
    card.set_author(
        name=f"r/{post.subreddit}",
        url=f"https://www.reddit.com/r/{post.subreddit}/new/",
        icon_url="https://www.redditstatic.com/desktop2x/img/favicon/android-icon-192x192.png",
    )
    card.add_field(name="Cre", value=f"u/{post.author}", inline=True)
    card.add_field(
        name="Thời gian đăng",
        value=f"<t:{int(post.created_at.timestamp())}:R>",
        inline=True,
    )
    card.add_field(
        name="Liên kết",
        value=f"[Xem bài viết trên Reddit]({post.permalink})",
        inline=False,
    )
    if post.flair:
        card.add_field(name="Chủ đề", value=post.flair[:1024], inline=True)
    if post.image_url:
        card.set_image(url=post.image_url)
    card.set_footer(text="Reddit • Bài viết mới")
    return card


class RedditCog(commands.Cog):
    reddit = app_commands.Group(
        name="reddit",
        description="Theo dõi bài viết mới trên Reddit",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    def __init__(self, bot: BlastBot) -> None:
        self.bot = bot
        self.client = RedditClient(bot.app.settings)
        self.poll.change_interval(seconds=bot.app.settings.reddit_poll_interval)
        self.configured = bool(
            self.client.has_oauth_credentials
            or bot.app.settings.reddit_keyless_fallback
        )
        if self.configured:
            self.poll.start()
            logger.info("Reddit monitoring started in %s mode", self.client.mode)
        else:
            logger.warning(
                "Reddit monitoring is paused: OAuth credentials are missing and RSS fallback is disabled"
            )

    async def cog_unload(self) -> None:
        self.poll.cancel()
        await self.client.close()

    @reddit.command(name="add", description="Theo dõi bài mới của một cộng đồng Reddit")
    @app_commands.describe(
        subreddit="Ví dụ: python hoặc r/python", channel="Kênh nhận bài mới"
    )
    @require_guild_permissions(manage_guild=True)
    async def add(
        self,
        interaction: discord.Interaction,
        subreddit: str,
        channel: discord.TextChannel,
    ) -> None:
        if interaction.guild_id is None:
            return
        if not self.configured:
            await interaction.response.send_message(
                embed=error(
                    "Reddit chưa được cấu hình",
                    "Hãy bật `REDDIT_KEYLESS_FALLBACK` hoặc cấu hình Reddit OAuth, sau đó restart bot.",
                ),
                ephemeral=True,
            )
            return
        name = normalize_subreddit(subreddit)
        await interaction.response.defer(ephemeral=True)
        try:
            posts = await self.client.newest(name, limit=1)
        except (aiohttp.ClientError, RuntimeError) as exc:
            logger.warning("Could not validate subreddit %s: %s", name, exc)
            await interaction.followup.send(
                embed=error(
                    "Không thể kết nối Reddit",
                    f"Đang dùng **{self.client.mode}**. Kiểm tra tên cộng đồng hoặc thử lại sau nếu Reddit đang giới hạn request.",
                ),
                ephemeral=True,
            )
            return
        subscription_id = await self.bot.app.reddit.add(
            interaction.guild_id, channel.id, name
        )
        if posts:
            await self.bot.app.reddit_repo.mark_seen(subscription_id, posts[0].id)
        await interaction.followup.send(
            embed=success(
                "Đã bật theo dõi Reddit",
                f"Bài mới từ **r/{name}** sẽ được gửi vào {channel.mention}.\n"
                f"Chế độ: **{self.client.mode}** · ID: `{subscription_id}`",
            ),
            ephemeral=True,
        )

    @reddit.command(name="list", description="Xem các cộng đồng Reddit đang theo dõi")
    @require_guild_permissions(manage_guild=True)
    async def list_subscriptions(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            return
        rows = await self.bot.app.reddit_repo.list_for_guild(interaction.guild_id)
        if not rows:
            await interaction.response.send_message(
                embed=info("Theo dõi Reddit", "Chưa có cộng đồng nào được theo dõi."),
                ephemeral=True,
            )
            return
        lines = [
            f"`{row.id}` • **r/{row.subreddit}** → <#{row.channel_id}> • {'✅' if row.enabled else '⏸️'}"
            for row in rows
        ]
        await interaction.response.send_message(
            embed=info("Các cộng đồng Reddit", "\n".join(lines)), ephemeral=True
        )

    @reddit.command(name="remove", description="Ngừng theo dõi một cộng đồng Reddit")
    @require_guild_permissions(manage_guild=True)
    async def remove(
        self, interaction: discord.Interaction, subscription_id: int
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.reddit.remove(interaction.guild_id, subscription_id)
        await interaction.response.send_message(
            embed=success("Đã ngừng theo dõi", f"Đã xóa cấu hình `{subscription_id}`."),
            ephemeral=True,
        )

    @reddit.command(name="toggle", description="Bật hoặc tắt một cấu hình Reddit")
    @require_guild_permissions(manage_guild=True)
    async def toggle(
        self, interaction: discord.Interaction, subscription_id: int, enabled: bool
    ) -> None:
        if interaction.guild_id is None:
            return
        await self.bot.app.reddit.set_enabled(
            interaction.guild_id, subscription_id, enabled
        )
        await interaction.response.send_message(
            embed=success(
                "Đã cập nhật",
                f"Cấu hình `{subscription_id}` đã được {'bật' if enabled else 'tắt'}.",
            ),
            ephemeral=True,
        )

    @reddit.command(name="test", description="Gửi thử bài mới nhất vào kênh đã chọn")
    @require_guild_permissions(manage_guild=True)
    async def test(
        self,
        interaction: discord.Interaction,
        subreddit: str,
        channel: discord.TextChannel,
    ) -> None:
        if not self.configured:
            await interaction.response.send_message(
                embed=error(
                    "Reddit chưa được cấu hình",
                    "Hãy bật `REDDIT_KEYLESS_FALLBACK` hoặc cấu hình Reddit OAuth, sau đó restart bot.",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        name = normalize_subreddit(subreddit)
        try:
            posts = await self.client.newest(name, limit=1)
        except (aiohttp.ClientError, RuntimeError):
            await interaction.followup.send(
                embed=error(
                    "Không thể lấy bài",
                    "Không thể kết nối hoặc cộng đồng không tồn tại.",
                ),
                ephemeral=True,
            )
            return
        if not posts:
            await interaction.followup.send(
                embed=error(
                    "Không có bài viết", f"Không tìm thấy bài công khai trong r/{name}."
                ),
                ephemeral=True,
            )
            return
        await channel.send(embed=reddit_embed(posts[0]))
        await interaction.followup.send(
            embed=success("Đã gửi thử", f"Embed đã được gửi vào {channel.mention}."),
            ephemeral=True,
        )

    async def _deliver(self, row: RedditSubscription, posts: list[RedditPost]) -> None:
        if not posts:
            return
        if row.last_seen_post_id is None:
            await self.bot.app.reddit_repo.mark_seen(row.id, posts[0].id)
            return
        unseen: list[RedditPost] = []
        for post in posts:
            if post.id == row.last_seen_post_id:
                break
            unseen.append(post)
        if not unseen:
            return
        guild = self.bot.get_guild(row.guild_id)
        channel = guild.get_channel(row.channel_id) if guild else None
        if not isinstance(channel, discord.TextChannel):
            await self.bot.app.reddit_repo.set_enabled(row.guild_id, row.id, False)
            logger.warning(
                "Disabled Reddit feed with missing channel",
                extra={"guild_id": row.guild_id},
            )
            return
        last_sent_id = row.last_seen_post_id
        for post in reversed(unseen[-10:]):
            try:
                await channel.send(embed=reddit_embed(post))
            except discord.HTTPException:
                logger.exception(
                    "Failed to send Reddit post", extra={"guild_id": row.guild_id}
                )
                break
            last_sent_id = post.id
        if last_sent_id != row.last_seen_post_id:
            await self.bot.app.reddit_repo.mark_seen(row.id, last_sent_id)

    @tasks.loop(seconds=120)
    async def poll(self) -> None:
        rows = await self.bot.app.reddit_repo.list_enabled()
        grouped: dict[str, list[RedditSubscription]] = defaultdict(list)
        for row in rows:
            grouped[row.subreddit].append(row)
        try:
            fetched = await self.client.newest_many(list(grouped))
        except (aiohttp.ClientError, RuntimeError):
            logger.exception("Failed to poll Reddit feeds")
            return
        for subreddit, subscriptions in grouped.items():
            posts = fetched.get(subreddit, [])
            for row in subscriptions:
                await self._deliver(row, posts)

    @poll.before_loop
    async def before_poll(self) -> None:
        await self.bot.wait_until_ready()

    @poll.error
    async def poll_error(self, exception: BaseException) -> None:
        logger.exception("Reddit polling task failed", exc_info=exception)


async def setup(bot: BlastBot) -> None:
    await bot.add_cog(RedditCog(bot))
