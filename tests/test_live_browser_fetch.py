"""Contracts for optional headless browser page fetching."""

from __future__ import annotations

import asyncio


def test_fetch_page_text_prefers_plain_http(monkeypatch) -> None:
    from skill.retrieval.live.clients import browser_fetch
    from skill.retrieval.live.clients import http as http_client

    observed = {"browser_called": False}

    async def _fake_fetch_text(**_: object) -> str:
        return "<html><body><main><h1>Alpha</h1><p>Primary page text.</p></main></body></html>"

    async def _fake_browser_fetch(**_: object) -> str:
        observed["browser_called"] = True
        return "<html><body><main><p>Browser page text.</p></main></body></html>"

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)
    monkeypatch.setattr(browser_fetch, "_fetch_with_browser", _fake_browser_fetch)

    content = asyncio.run(
        browser_fetch.fetch_page_text(
            url="https://example.com/page",
            browser_enabled=True,
            browser_headless=True,
        )
    )

    assert "Primary page text." in content
    assert observed["browser_called"] is False


def test_fetch_page_text_uses_browser_when_http_fails(monkeypatch) -> None:
    from skill.retrieval.live.clients import browser_fetch
    from skill.retrieval.live.clients import http as http_client

    observed = {"browser_called": False}

    async def _fake_fetch_text(**_: object) -> str:
        raise TimeoutError("plain HTTP timed out")

    async def _fake_browser_fetch(**_: object) -> str:
        observed["browser_called"] = True
        return "<html><body><main><p>Browser page text.</p></main></body></html>"

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)
    monkeypatch.setattr(browser_fetch, "_fetch_with_browser", _fake_browser_fetch)

    content = asyncio.run(
        browser_fetch.fetch_page_text(
            url="https://example.com/page",
            browser_enabled=True,
            browser_headless=True,
        )
    )

    assert "Browser page text." in content
    assert observed["browser_called"] is True


def test_fetch_page_text_rejects_non_headless_browser_mode() -> None:
    from skill.retrieval.live.clients.browser_fetch import fetch_page_text

    try:
        asyncio.run(
            fetch_page_text(
                url="https://example.com/page",
                browser_enabled=True,
                browser_headless=False,
            )
        )
    except ValueError as exc:
        assert "headless" in str(exc).lower()
    else:
        raise AssertionError("Expected non-headless browser mode to be rejected")


def test_extract_page_content_clips_output_to_safe_bounds() -> None:
    from skill.retrieval.live.parsers.page_content import extract_page_content

    html = (
        "<html><body><main><h1>Alpha</h1><p>"
        + ("word " * 5000)
        + "</p></main></body></html>"
    )

    content = extract_page_content(html, max_chars=120)

    assert content.startswith("Alpha")
    assert len(content) <= 120
