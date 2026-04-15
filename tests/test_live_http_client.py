"""Contracts for shared live HTTP timeout behavior."""

from __future__ import annotations

import asyncio
import importlib
import time

import pytest


def test_fetch_text_enforces_total_wall_clock_timeout(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client

    class _FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, *args: object, **kwargs: object):
            await asyncio.sleep(0.2)
            raise AssertionError("request should have been cancelled by timeout")

    monkeypatch.setattr(http_client.httpx, "AsyncClient", _FakeAsyncClient)

    started_at = time.perf_counter()
    with pytest.raises(TimeoutError):
        asyncio.run(
            http_client.fetch_text(
                url="https://example.com/slow",
                timeout=0.05,
            )
        )
    elapsed = time.perf_counter() - started_at

    assert elapsed < 0.15


def test_fetch_json_enforces_total_wall_clock_timeout(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client

    class _FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, *args: object, **kwargs: object):
            await asyncio.sleep(0.2)
            raise AssertionError("request should have been cancelled by timeout")

    monkeypatch.setattr(http_client.httpx, "AsyncClient", _FakeAsyncClient)

    started_at = time.perf_counter()
    with pytest.raises(TimeoutError):
        asyncio.run(
            http_client.fetch_json(
                url="https://example.com/slow.json",
                timeout=0.05,
            )
        )
    elapsed = time.perf_counter() - started_at

    assert elapsed < 0.15


def test_fetch_json_reuses_persistent_academic_cache_across_module_reload(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("WASC_LIVE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("WASC_LIVE_ACADEMIC_CACHE_TTL_SECONDS", "600")

    from skill.retrieval.live.clients import http as http_client

    observed_calls = 0

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return {"results": [{"title": "Grounded Search Evidence Packing"}]}

    class _FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> _FakeResponse:
            nonlocal observed_calls
            observed_calls += 1
            return _FakeResponse()

    monkeypatch.setattr(http_client.httpx, "AsyncClient", _FakeAsyncClient)

    first_payload = asyncio.run(
        http_client.fetch_json(
            url="https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": "grounded search evidence packing", "limit": "5"},
            timeout=0.2,
            cache_scope="academic",
        )
    )

    reloaded_http_client = importlib.reload(http_client)

    class _UnexpectedAsyncClient:
        def __init__(self, **_: object) -> None:
            raise AssertionError("persistent academic cache should avoid a second network call")

    monkeypatch.setattr(reloaded_http_client.httpx, "AsyncClient", _UnexpectedAsyncClient)

    cached_payload = asyncio.run(
        reloaded_http_client.fetch_json(
            url="https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": "grounded search evidence packing", "limit": "5"},
            timeout=0.2,
            cache_scope="academic",
        )
    )

    assert observed_calls == 1
    assert cached_payload == first_payload


def test_fetch_text_limited_reuses_search_cache_for_identical_requests(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("WASC_LIVE_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("WASC_LIVE_SEARCH_CACHE_TTL_SECONDS", "600")

    from skill.retrieval.live.clients import http as http_client

    observed_calls = 0

    class _FakeStreamResponse:
        async def __aenter__(self) -> "_FakeStreamResponse":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_text(self):
            yield "<html><body>duckduckgo result page</body></html>"

    class _FakeAsyncClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        def stream(self, *args: object, **kwargs: object) -> _FakeStreamResponse:
            nonlocal observed_calls
            observed_calls += 1
            return _FakeStreamResponse()

    monkeypatch.setattr(http_client.httpx, "AsyncClient", _FakeAsyncClient)

    first_html = asyncio.run(
        http_client.fetch_text_limited(
            url="https://html.duckduckgo.com/html/",
            params={"q": "battery recycling market share 2025"},
            timeout=0.2,
            max_chars=10_000,
            cache_scope="search",
        )
    )
    second_html = asyncio.run(
        http_client.fetch_text_limited(
            url="https://html.duckduckgo.com/html/",
            params={"q": "battery recycling market share 2025"},
            timeout=0.2,
            max_chars=10_000,
            cache_scope="search",
        )
    )

    assert observed_calls == 1
    assert second_html == first_html
