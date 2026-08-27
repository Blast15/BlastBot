from __future__ import annotations

import html
import io
from datetime import UTC

import discord


async def build_transcript_file(
    channel: discord.TextChannel,
    *,
    message_limit: int,
) -> discord.File:
    """Build a bounded HTML transcript for a ticket channel."""
    rows: list[str] = []
    async for message in channel.history(limit=message_limit, oldest_first=True):
        created = message.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        author = html.escape(str(message.author))
        content = html.escape(message.clean_content or "")
        attachments = "".join(
            f'<div class="attachment"><a href="{html.escape(item.url, quote=True)}">'
            f"{html.escape(item.filename)}</a></div>"
            for item in message.attachments
        )
        rows.append(
            '<article class="message">'
            f'<div class="meta"><strong>{author}</strong> · {created}</div>'
            f'<div class="content">{content}</div>{attachments}'
            "</article>"
        )

    body = "\n".join(rows) or '<p class="empty">Không có tin nhắn.</p>'
    document = f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transcript #{html.escape(channel.name)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 32px auto; padding: 0 18px; background: #1e1f22; color: #dbdee1; }}
h1 {{ color: #f2f3f5; }}
.message {{ padding: 12px 0; border-bottom: 1px solid #313338; }}
.meta {{ color: #b5bac1; font-size: 13px; margin-bottom: 5px; }}
.content {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
a {{ color: #00a8fc; }}
.attachment {{ margin-top: 5px; }}
.empty {{ color: #b5bac1; }}
</style>
</head>
<body>
<h1>#{html.escape(channel.name)}</h1>
{body}
</body>
</html>"""
    payload = io.BytesIO(document.encode("utf-8"))
    return discord.File(payload, filename=f"transcript-{channel.id}.html")
