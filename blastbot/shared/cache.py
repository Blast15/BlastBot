from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class _Entry(Generic[V]):
    value: V
    expires_at: datetime


class TTLCache(Generic[K, V]):
    """Small bounded in-process cache. Database remains the source of truth."""

    def __init__(self, *, max_size: int, ttl: timedelta) -> None:
        if max_size < 1:
            raise ValueError("max_size must be positive")
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        self._max_size = max_size
        self._ttl = ttl
        self._items: OrderedDict[K, _Entry[V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if datetime.now(UTC) >= entry.expires_at:
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return entry.value

    def set(self, key: K, value: V) -> None:
        self._items[key] = _Entry(value=value, expires_at=datetime.now(UTC) + self._ttl)
        self._items.move_to_end(key)
        while len(self._items) > self._max_size:
            self._items.popitem(last=False)

    def invalidate(self, key: K) -> None:
        self._items.pop(key, None)

    def clear(self) -> None:
        self._items.clear()
