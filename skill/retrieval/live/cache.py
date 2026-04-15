"""Small in-memory TTL cache for live retrieval helpers."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
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


class FileTTLCache(Generic[ValueT]):
    """Small JSON-backed TTL cache shared across fresh processes."""

    def __init__(self, *, root_dir: Path, namespace: str) -> None:
        self._root_dir = root_dir / namespace
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._clock = time.time

    def _path_for_key(self, key: str) -> Path:
        digest = sha256(key.encode("utf-8")).hexdigest()
        return self._root_dir / f"{digest}.json"

    def get(self, key: str) -> ValueT | None:
        path = self._path_for_key(key)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

        expires_at = float(payload.get("expires_at", 0.0))
        if expires_at <= self._clock():
            try:
                path.unlink()
            except OSError:
                pass
            return None

        return payload.get("value")  # type: ignore[return-value]

    def set(self, key: str, value: ValueT, *, ttl_seconds: int) -> None:
        path = self._path_for_key(key)
        tmp_path = path.with_suffix(".tmp")
        payload = {
            "expires_at": self._clock() + max(0, ttl_seconds),
            "value": value,
        }
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )
        tmp_path.replace(path)
