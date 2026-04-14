"""Environment-backed runtime config for live retrieval support."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


LiveRetrievalMode = Literal["live", "fixture"]

_TRUTHY = {"1", "true", "yes", "on"}


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in _TRUTHY


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return int(value)


def _read_mode_env(name: str, default: LiveRetrievalMode) -> LiveRetrievalMode:
    value = (os.getenv(name) or "").strip().lower()
    if not value:
        return default
    if value not in {"live", "fixture"}:
        raise ValueError(f"{name} must be 'live' or 'fixture'")
    return value  # type: ignore[return-value]


def _read_search_engines_env() -> tuple[str, ...]:
    raw = os.getenv("WASC_LIVE_SEARCH_ENGINES", "")
    if not raw.strip():
        return ("duckduckgo", "bing", "google")
    engines = tuple(
        part.strip().lower()
        for part in raw.split(",")
        if part.strip()
    )
    return engines or ("duckduckgo", "bing", "google")


@dataclass(frozen=True)
class LiveRetrievalConfig:
    mode: LiveRetrievalMode = "live"
    search_engines: tuple[str, ...] = ("duckduckgo", "bing", "google")
    browser_enabled: bool = False
    browser_headless: bool = True
    fixture_shortcuts_enabled: bool = True
    search_cache_ttl_seconds: int = 1800
    page_cache_ttl_seconds: int = 3600
    academic_cache_ttl_seconds: int = 86400

    @classmethod
    def from_env(cls) -> "LiveRetrievalConfig":
        return cls(
            mode=_read_mode_env("WASC_RETRIEVAL_MODE", "live"),
            search_engines=_read_search_engines_env(),
            browser_enabled=_read_bool_env("WASC_LIVE_BROWSER_ENABLED", False),
            browser_headless=_read_bool_env("WASC_LIVE_BROWSER_HEADLESS", True),
            fixture_shortcuts_enabled=_read_bool_env(
                "WASC_LIVE_FIXTURE_SHORTCUTS_ENABLED",
                True,
            ),
            search_cache_ttl_seconds=_read_int_env(
                "WASC_LIVE_SEARCH_CACHE_TTL_SECONDS",
                1800,
            ),
            page_cache_ttl_seconds=_read_int_env(
                "WASC_LIVE_PAGE_CACHE_TTL_SECONDS",
                3600,
            ),
            academic_cache_ttl_seconds=_read_int_env(
                "WASC_LIVE_ACADEMIC_CACHE_TTL_SECONDS",
                86400,
            ),
        )
