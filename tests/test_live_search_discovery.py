"""Contracts for shared multi-engine web discovery."""

from __future__ import annotations

import asyncio

import httpx
import pytest


_DDG_HTML = """
<html>
  <body>
    <div class="result">
      <a class="result__a" href="https://example.com/alpha">Alpha Result</a>
      <a class="result__snippet">Alpha snippet from DuckDuckGo.</a>
    </div>
    <div class="result">
      <a class="result__a" href="https://example.com/beta">Beta Result</a>
      <a class="result__snippet">Beta snippet from DuckDuckGo.</a>
    </div>
  </body>
</html>
"""

_DDG_REDIRECT_HTML = """
<html>
  <body>
    <div class="result">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.deloitte.com%2Fus%2Fen%2Finsights%2Findustry%2Ftechnology%2Ftechnology-media-telecom-outlooks%2Fsemiconductor-industry-outlook.html">
        2026 Semiconductor Industry Outlook | Deloitte Insights
      </a>
      <a class="result__snippet">Deloitte expects AI-driven semiconductor demand to remain strong in 2026.</a>
    </div>
  </body>
</html>
"""

_BING_HTML = """
<html>
  <body>
    <ol>
      <li class="b_algo">
        <h2><a href="https://example.com/beta">Beta Result</a></h2>
        <div class="b_caption"><p>Beta snippet from Bing.</p></div>
      </li>
      <li class="b_algo">
        <h2><a href="https://example.com/gamma">Gamma Result</a></h2>
        <div class="b_caption"><p>Gamma snippet from Bing.</p></div>
      </li>
    </ol>
  </body>
</html>
"""

_BING_REDIRECT_HTML = """
<html>
  <body>
    <ol>
      <li class="b_algo">
        <h2>
          <a href="https://www.bing.com/ck/a?!&&p=abc&u=a1aHR0cHM6Ly9ldXItbGV4LmV1cm9wYS5ldS9sZWdhbC1jb250ZW50L0VOL1RYVC9IVE1MLz9xdXJpPWNl%0AQ0VMSVg6MzIwMjQwUjE2ODk&ntb=1">
            AI Act obligations
          </a>
        </h2>
        <div class="b_caption"><p>Official EU policy page.</p></div>
      </li>
    </ol>
  </body>
</html>
"""

_GOOGLE_HTML = """
<html>
  <body>
    <div class="g">
      <a href="https://example.com/delta">Delta Result</a>
      <div class="VwiC3b">Delta snippet from Google.</div>
    </div>
  </body>
</html>
"""

_GOOGLE_NEWS_RSS = """
<rss version="2.0">
  <channel>
    <item>
      <title>Battery Recycling Global Markets Report 2025-2030 - Yahoo Finance</title>
      <link>https://news.google.com/rss/articles/example-1</link>
      <pubDate>Tue, 04 Feb 2025 08:00:00 GMT</pubDate>
      <description><![CDATA[
        <a href="https://news.google.com/rss/articles/example-1">Battery Recycling Global Markets Report 2025-2030</a>
        <font color="#6f6f6f">Yahoo Finance</font>
      ]]></description>
      <source url="https://finance.yahoo.com">Yahoo Finance</source>
    </item>
    <item>
      <title>Advanced Packaging Bottleneck Spurs Investment - The Futurum Group</title>
      <link>https://news.google.com/rss/articles/example-2</link>
      <pubDate>Wed, 05 Feb 2025 08:00:00 GMT</pubDate>
      <description><![CDATA[
        <a href="https://news.google.com/rss/articles/example-2">Advanced Packaging Bottleneck Spurs Investment</a>
        <font color="#6f6f6f">The Futurum Group</font>
      ]]></description>
      <source url="https://futurumgroup.com">The Futurum Group</source>
    </item>
  </channel>
</rss>
"""

_BING_RSS = """
<rss version="2.0">
  <channel>
    <item>
      <title>TSMC expands CoWoS capacity with Nvidia booking over half for 2026-27</title>
      <link>http://www.digitimes.com/news/a20251210PD210/tsmc-cowos-capacity-2026.html</link>
      <description>TSMC expands CoWoS capacity with Nvidia booking over half for 2026-27 as advanced packaging supply remains tight.</description>
      <pubDate>Wed, 10 Dec 2025 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_search_candidates_duckduckgo_returns_normalized_candidates(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text_limited(**_: object) -> str:
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(search_candidates(query="battery recycling", engine="duckduckgo"))

    assert [candidate.title for candidate in candidates] == ["Alpha Result", "Beta Result"]
    assert candidates[0].snippet == "Alpha snippet from DuckDuckGo."
    assert all(candidate.engine == "duckduckgo" for candidate in candidates)


def test_search_candidates_duckduckgo_decodes_redirect_candidates(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text_limited(**_: object) -> str:
        return _DDG_REDIRECT_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(
        search_candidates(query="semiconductor outlook", engine="duckduckgo")
    )

    assert len(candidates) == 1
    assert (
        candidates[0].url
        == "https://www.deloitte.com/us/en/insights/industry/technology/"
        "technology-media-telecom-outlooks/semiconductor-industry-outlook.html"
    )


def test_search_candidates_bing_returns_normalized_candidates(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text_limited(**_: object) -> str:
        return _BING_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(search_candidates(query="battery recycling", engine="bing"))

    assert [candidate.title for candidate in candidates] == ["Beta Result", "Gamma Result"]
    assert candidates[1].snippet == "Gamma snippet from Bing."
    assert all(candidate.engine == "bing" for candidate in candidates)


def test_search_multi_engine_tolerates_google_failure(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_multi_engine

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        if "google" in url:
            raise TimeoutError("google timed out")
        if "bing" in url:
            return _BING_HTML
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(
        search_multi_engine(
            query="battery recycling",
            engines=("duckduckgo", "bing", "google"),
            max_results=5,
        )
    )

    assert candidates
    assert all(candidate.engine in {"duckduckgo", "bing"} for candidate in candidates)
    assert "Delta Result" not in [candidate.title for candidate in candidates]


def test_search_multi_engine_dedupes_urls_across_engines(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_multi_engine

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        if "google" in url:
            return _GOOGLE_HTML
        if "bing" in url:
            return _BING_HTML
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(
        search_multi_engine(
            query="battery recycling",
            engines=("duckduckgo", "bing", "google"),
            max_results=10,
        )
    )

    assert [candidate.url for candidate in candidates] == [
        "https://example.com/alpha",
        "https://example.com/beta",
        "https://example.com/gamma",
        "https://example.com/delta",
    ]


def test_search_candidates_bing_unwraps_redirect_urls(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text_limited(**_: object) -> str:
        return _BING_REDIRECT_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(search_candidates(query="AI Act obligations", engine="bing"))

    assert len(candidates) == 1
    assert candidates[0].url.startswith("https://eur-lex.europa.eu/")


def test_search_candidates_bing_rss_does_not_retry_timeout_backups(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    call_count = 0

    async def _fake_fetch_text_limited(**_: object) -> str:
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("bing rss timed out")

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    with pytest.raises(httpx.TimeoutException):
        asyncio.run(search_candidates(query="CoWoS capacity 2026", engine="bing_rss"))

    assert call_count == 1


def test_search_candidates_google_news_rss_uses_source_urls(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text_limited(**_: object) -> str:
        return _GOOGLE_NEWS_RSS

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(
        search_candidates(query="battery recycling market share 2025", engine="google_news_rss")
    )

    assert [candidate.url for candidate in candidates] == [
        "https://news.google.com/rss/articles/example-1",
        "https://news.google.com/rss/articles/example-2",
    ]
    assert [candidate.source_url for candidate in candidates] == [
        "https://finance.yahoo.com",
        "https://futurumgroup.com",
    ]
    assert candidates[0].snippet == (
        "Battery Recycling Global Markets Report 2025-2030 Yahoo Finance"
        " | Source: Yahoo Finance | Tue, 04 Feb 2025 08:00:00 GMT"
    )
    assert all(candidate.engine == "google_news_rss" for candidate in candidates)


def test_search_candidates_google_news_rss_uses_zh_cn_locale_for_cjk_queries(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    observed_params: dict[str, object] = {}

    async def _fake_fetch_text_limited(**kwargs: object) -> str:
        observed_params.update(dict(kwargs.get("params", {})))
        return _GOOGLE_NEWS_RSS

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    asyncio.run(
        search_candidates(
            query="\u52a8\u529b\u7535\u6c60\u56de\u6536\u5e02\u573a\u4efd\u989d\u9884\u6d4b",
            engine="google_news_rss",
        )
    )

    assert observed_params["hl"] == "zh-CN"
    assert observed_params["gl"] == "CN"
    assert observed_params["ceid"] == "CN:zh-Hans"


def test_search_candidates_google_news_rss_keeps_us_locale_for_ascii_queries(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    observed_params: dict[str, object] = {}

    async def _fake_fetch_text_limited(**kwargs: object) -> str:
        observed_params.update(dict(kwargs.get("params", {})))
        return _GOOGLE_NEWS_RSS

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    asyncio.run(
        search_candidates(
            query="battery recycling market share 2025",
            engine="google_news_rss",
        )
    )

    assert observed_params["hl"] == "en-US"
    assert observed_params["gl"] == "US"
    assert observed_params["ceid"] == "US:en"


def test_search_candidates_bing_rss_returns_direct_urls_and_snippets(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text_limited(**_: object) -> str:
        return _BING_RSS

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(search_candidates(query="CoWoS capacity 2026", engine="bing_rss"))

    assert len(candidates) == 1
    assert candidates[0].engine == "bing_rss"
    assert candidates[0].url == (
        "https://www.digitimes.com/news/a20251210PD210/tsmc-cowos-capacity-2026.html"
    )
    assert "advanced packaging supply remains tight" in candidates[0].snippet


def test_search_candidates_retries_bing_connect_errors(monkeypatch) -> None:
    import httpx

    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    attempts = 0

    async def _flaky_fetch_text_limited(**_: object) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise httpx.ConnectError("connect failed")
        return _BING_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _flaky_fetch_text_limited)

    candidates = asyncio.run(search_candidates(query="battery recycling", engine="bing"))

    assert attempts == 2
    assert len(candidates) == 2
    assert candidates[0].title == "Beta Result"


def test_search_multi_engine_fetches_engines_concurrently(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_multi_engine

    started_urls: list[str] = []
    all_started = asyncio.Event()

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        started_urls.append(url)
        if len(started_urls) == 3:
            all_started.set()
        await all_started.wait()
        if "google" in url:
            return _GOOGLE_HTML
        if "bing" in url:
            return _BING_HTML
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(
        asyncio.wait_for(
            search_multi_engine(
                query="battery recycling",
                engines=("duckduckgo", "bing", "google"),
                max_results=10,
            ),
            timeout=0.2,
        )
    )

    assert len(started_urls) == 3
    assert [candidate.url for candidate in candidates] == [
        "https://example.com/alpha",
        "https://example.com/beta",
        "https://example.com/gamma",
        "https://example.com/delta",
    ]


def test_search_multi_engine_can_stop_after_first_success(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_multi_engine

    started_urls: list[str] = []
    cancelled_urls: list[str] = []

    async def _fake_fetch_text_limited(*, url: str, **_: object) -> str:
        if "duckduckgo" in url:
            await asyncio.sleep(0.01)
            return _DDG_HTML
        started_urls.append(url)
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled_urls.append(url)
            raise
        return _BING_HTML if "bing" in url else _GOOGLE_HTML

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)

    candidates = asyncio.run(
        asyncio.wait_for(
            search_multi_engine(
                query="battery recycling",
                engines=("duckduckgo", "bing", "google"),
                max_results=5,
                stop_after_first_success=True,
            ),
            timeout=0.2,
        )
    )

    assert candidates
    assert all(candidate.engine == "duckduckgo" for candidate in candidates)
    assert len(started_urls) == 2
    assert sorted(cancelled_urls) == sorted(started_urls)


def test_search_candidates_uses_limited_fetch_for_live_serp_pages(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    observed_calls: list[tuple[str, int]] = []

    async def _fake_fetch_text_limited(
        *,
        url: str,
        max_chars: int,
        **_: object,
    ) -> str:
        observed_calls.append((url, max_chars))
        return _BING_HTML

    async def _unexpected_fetch_text(**_: object) -> str:
        raise AssertionError("search_candidates should use fetch_text_limited for SERP pages")

    monkeypatch.setattr(http_client, "fetch_text_limited", _fake_fetch_text_limited)
    monkeypatch.setattr(http_client, "fetch_text", _unexpected_fetch_text)

    candidates = asyncio.run(search_candidates(query="battery recycling", engine="bing"))

    assert [candidate.title for candidate in candidates] == ["Beta Result", "Gamma Result"]
    assert observed_calls == [("https://www.bing.com/search", 120000)]
