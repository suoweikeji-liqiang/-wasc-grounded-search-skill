"""Contracts for shared live HTTP timeout behavior."""

from __future__ import annotations

import asyncio
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
