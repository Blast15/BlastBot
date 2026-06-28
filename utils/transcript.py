"""HTML transcript cho ticket."""

import html
import io

import discord


async def generate_transcript(
    channel: discord.TextChannel, limit: int = 2000
) -> discord.File:
    messages = [m async for m in channel.history(limit=limit, oldest_first=True)]
    rows = []
    for msg in messages:
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = html.escape(str(msg.author))
        content = html.escape(msg.content) if msg.content else ""
        atts = "".join(
            f'<div class="att"><a href="{html.escape(a.url)}">{html.escape(a.filename)}</a></div>'
            for a in msg.attachments
        )
        emb = '<div class="embed">[embed]</div>' if msg.embeds else ""
        rows.append(
            f'<div class="msg"><span class="time">{ts}</span> '
            f'<span class="author">{author}</span>'
            f'<div class="content">{content}{atts}{emb}</div></div>'
        )
    body = "\n".join(rows) or "<p>Không có tin nhắn.</p>"
    name = html.escape(channel.name)
    limit_warning = (
        f"<p style='color:#faa61a;'>⚠️ Chỉ hiển thị {limit} tin nhắn gần nhất.</p>"
        if len(messages) >= limit
        else ""
    )
    doc = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>Transcript - {name}</title><style>
body{{background:#36393f;color:#dcddde;font-family:Arial,sans-serif;padding:20px}}
h1{{color:#fff}}.msg{{padding:6px 0;border-bottom:1px solid #2f3136}}
.time{{color:#72767d;font-size:12px;margin-right:8px}}
.author{{color:#7289da;font-weight:bold}}
.content{{margin-top:2px;white-space:pre-wrap}}
.att a{{color:#00aff4}}.embed{{color:#b9bbbe;font-style:italic}}
</style></head><body><h1>Transcript: #{name}</h1>
<p>Số tin nhắn: {len(messages)}</p>{limit_warning}<hr>{body}</body></html>"""
    return discord.File(
        io.BytesIO(doc.encode("utf-8")), filename=f"transcript-{channel.name}.html"
    )
