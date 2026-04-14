"""Small in-memory TTL cache for live retrieval helpers."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar


ValueT = TypeVar("ValueT")


@dataclass
class _CacheEntry(Generic[ValueT]):
    value: ValueT
    expires_at: float


class TTLCache(Generic[ValueT]):
    def __init__(self, *, max_entries: int = 128) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries: "OrderedDict[str, _CacheEntry[ValueT]]" = OrderedDict()
        self._clock = time.monotonic

    def _purge_expired(self) -> None:
        now = self._clock()
        expired = [
            key
            for key, entry in self._entries.items()
            if entry.expires_at <= now
        ]
        for key in expired:
            self._entries.pop(key, None)

    def get(self, key: str) -> ValueT | None:
        self._purge_expired()
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._entries.move_to_end(key)
        return entry.value

    def set(self, key: str, value: ValueT, *, ttl_seconds: int) -> None:
        self._purge_expired()
        self._entries[key] = _CacheEntry(
            value=value,
            expires_at=self._clock() + max(0, ttl_seconds),
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
