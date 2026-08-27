from __future__ import annotations

import re

from blastbot.core.errors import ValidationError


def require_text(value: str, *, minimum: int = 1, maximum: int = 2000) -> str:
    text = value.strip()
    if not minimum <= len(text) <= maximum:
        raise ValidationError(
            f"text length {len(text)} outside [{minimum}, {maximum}]",
            f"Văn bản phải có từ {minimum} đến {maximum} ký tự.",
        )
    return text


def require_range(value: int, *, minimum: int, maximum: int, name: str) -> int:
    if not minimum <= value <= maximum:
        raise ValidationError(
            f"{name} outside [{minimum}, {maximum}]",
            f"{name} phải từ {minimum} đến {maximum}.",
        )
    return value


def normalize_channel_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "-")
    normalized = re.sub(r"[^a-z0-9-_]", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return (normalized or "channel")[:100]


def normalize_tag_id(value: str) -> str:
    text = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", text):
        raise ValidationError(
            f"invalid tag id: {value!r}",
            "Tag ID chỉ được chứa a-z, 0-9, dấu gạch ngang/gạch dưới và tối đa 64 ký tự.",
        )
    return text
