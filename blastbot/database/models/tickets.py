from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from blastbot.database.base import Base, utcnow


class TicketSettings(Base):
    __tablename__ = "ticket_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transcript_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    ticket_limit: Mapped[int] = mapped_column(Integer, default=5)
    welcome_message: Mapped[str | None] = mapped_column(Text)
    claim_mode: Mapped[str] = mapped_column(String(32), default="reply_only")
    autoclose_hours: Mapped[int] = mapped_column(Integer, default=0)
    ticket_counter: Mapped[int] = mapped_column(Integer, default=0)


class TicketStaff(Base):
    __tablename__ = "ticket_staff"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(32), primary_key=True)
    is_role: Mapped[bool] = mapped_column(Boolean)


class TicketPanel(Base):
    __tablename__ = "ticket_panels"

    panel_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    color: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[int] = mapped_column(BigInteger)
    button_label: Mapped[str] = mapped_column(String(80))
    button_emoji: Mapped[str | None] = mapped_column(String(128))
    welcome_message: Mapped[str | None] = mapped_column(Text)
    mention_on_open: Mapped[str] = mapped_column(Text, default="[]")
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    channel_id: Mapped[int | None] = mapped_column(BigInteger)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("uq_tickets_guild_number", "guild_id", "number", unique=True),
        Index("uq_tickets_channel_id", "channel_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    number: Mapped[int] = mapped_column(Integer)
    channel_id: Mapped[int | None] = mapped_column(BigInteger)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    panel_id: Mapped[int | None] = mapped_column(Integer)
    claimed_by: Mapped[int | None] = mapped_column(BigInteger)
    open: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(Text)
    last_message_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    excluded_autoclose: Mapped[bool] = mapped_column(Boolean, default=False)


class TicketMember(Base):
    __tablename__ = "ticket_members"

    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class TicketBlacklist(Base):
    __tablename__ = "ticket_blacklist"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_role: Mapped[bool] = mapped_column(Boolean)


class TicketTag(Base):
    __tablename__ = "ticket_tags"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tag_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[str] = mapped_column(Text)
