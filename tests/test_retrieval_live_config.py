"""Live retrieval config and cache contracts."""

from __future__ import annotations

import time


def test_live_retrieval_config_defaults_to_live_mode(monkeypatch) -> None:
    from skill.config.live_retrieval import LiveRetrievalConfig

    monkeypatch.delenv("WASC_RETRIEVAL_MODE", raising=False)
    monkeypatch.delenv("WASC_LIVE_SEARCH_ENGINES", raising=False)
    monkeypatch.delenv("WASC_LIVE_BROWSER_ENABLED", raising=False)
    monkeypatch.delenv("WASC_LIVE_BROWSER_HEADLESS", raising=False)

    config = LiveRetrievalConfig.from_env()

    assert config.mode == "live"
    assert config.search_engines == ("duckduckgo", "bing", "google")
    assert config.browser_enabled is False
    assert config.browser_headless is True


def test_live_retrieval_config_reads_overrides(monkeypatch) -> None:
    from skill.config.live_retrieval import LiveRetrievalConfig

    monkeypatch.setenv("WASC_RETRIEVAL_MODE", "fixture")
    monkeypatch.setenv("WASC_LIVE_SEARCH_ENGINES", "bing,duckduckgo")
    monkeypatch.setenv("WASC_LIVE_BROWSER_ENABLED", "1")
    monkeypatch.setenv("WASC_LIVE_BROWSER_HEADLESS", "true")
    monkeypatch.setenv("WASC_LIVE_SEARCH_CACHE_TTL_SECONDS", "12")
    monkeypatch.setenv("WASC_LIVE_PAGE_CACHE_TTL_SECONDS", "34")
    monkeypatch.setenv("WASC_LIVE_ACADEMIC_CACHE_TTL_SECONDS", "56")

    config = LiveRetrievalConfig.from_env()

    assert config.mode == "fixture"
    assert config.search_engines == ("bing", "duckduckgo")
    assert config.browser_enabled is True
    assert config.browser_headless is True
    assert config.search_cache_ttl_seconds == 12
    assert config.page_cache_ttl_seconds == 34
    assert config.academic_cache_ttl_seconds == 56


def test_live_retrieval_ttl_cache_expires_entries() -> None:
    from skill.retrieval.live.cache import TTLCache

    cache = TTLCache(max_entries=2)

    cache.set("alpha", {"value": 1}, ttl_seconds=1)
    assert cache.get("alpha") == {"value": 1}

    cache._clock = lambda: time.monotonic() + 2  # type: ignore[method-assign]
    assert cache.get("alpha") is None


def test_live_retrieval_ttl_cache_evicts_oldest_entry_when_bounded() -> None:
    from skill.retrieval.live.cache import TTLCache

    cache = TTLCache(max_entries=2)

    cache.set("alpha", 1, ttl_seconds=60)
    cache.set("beta", 2, ttl_seconds=60)
    cache.set("gamma", 3, ttl_seconds=60)

    assert cache.get("alpha") is None
    assert cache.get("beta") == 2
    assert cache.get("gamma") == 3
