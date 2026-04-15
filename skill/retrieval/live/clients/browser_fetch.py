"""Optional headless browser fallback for live page fetching."""

from __future__ import annotations

from skill.retrieval.live.clients import http as http_client
from skill.retrieval.live.parsers.page_content import extract_page_content


async def _fetch_with_browser(
    *,
    url: str,
    timeout_seconds: float,
    headless: bool,
) -> str:
    if not headless:
        raise ValueError("Browser fetch must remain headless")

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for browser fetching") from exc

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=int(timeout_seconds * 1000))
            return await page.content()
        finally:
            await browser.close()


async def fetch_page_text(
    *,
    url: str,
    browser_enabled: bool,
    browser_headless: bool,
    timeout_seconds: float = 10.0,
    max_chars: int = 4000,
) -> str:
    if browser_enabled and not browser_headless:
        raise ValueError("Only headless browser mode is supported")

    try:
        html = await http_client.fetch_text(
            url=url,
            timeout=timeout_seconds,
            cache_scope="page",
            cache_key=url,
        )
        content = extract_page_content(html, max_chars=max_chars)
        if content:
            return content
    except Exception:
        html = ""

    if not browser_enabled:
        return ""

    browser_html = await _fetch_with_browser(
        url=url,
        timeout_seconds=timeout_seconds,
        headless=browser_headless,
    )
    return extract_page_content(browser_html, max_chars=max_chars)
