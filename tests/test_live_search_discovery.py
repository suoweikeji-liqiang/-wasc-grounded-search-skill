"""Contracts for shared multi-engine web discovery."""

from __future__ import annotations

import asyncio


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


def test_search_candidates_duckduckgo_returns_normalized_candidates(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text(**_: object) -> str:
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)

    candidates = asyncio.run(search_candidates(query="battery recycling", engine="duckduckgo"))

    assert [candidate.title for candidate in candidates] == ["Alpha Result", "Beta Result"]
    assert candidates[0].snippet == "Alpha snippet from DuckDuckGo."
    assert all(candidate.engine == "duckduckgo" for candidate in candidates)


def test_search_candidates_bing_returns_normalized_candidates(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_candidates

    async def _fake_fetch_text(**_: object) -> str:
        return _BING_HTML

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)

    candidates = asyncio.run(search_candidates(query="battery recycling", engine="bing"))

    assert [candidate.title for candidate in candidates] == ["Beta Result", "Gamma Result"]
    assert candidates[1].snippet == "Gamma snippet from Bing."
    assert all(candidate.engine == "bing" for candidate in candidates)


def test_search_multi_engine_tolerates_google_failure(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_multi_engine

    async def _fake_fetch_text(*, url: str, **_: object) -> str:
        if "google" in url:
            raise TimeoutError("google timed out")
        if "bing" in url:
            return _BING_HTML
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)

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

    async def _fake_fetch_text(*, url: str, **_: object) -> str:
        if "google" in url:
            return _GOOGLE_HTML
        if "bing" in url:
            return _BING_HTML
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)

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

    async def _fake_fetch_text(**_: object) -> str:
        return _BING_REDIRECT_HTML

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)

    candidates = asyncio.run(search_candidates(query="AI Act obligations", engine="bing"))

    assert len(candidates) == 1
    assert candidates[0].url.startswith("https://eur-lex.europa.eu/")


def test_search_multi_engine_fetches_engines_concurrently(monkeypatch) -> None:
    from skill.retrieval.live.clients import http as http_client
    from skill.retrieval.live.clients.search_discovery import search_multi_engine

    started_urls: list[str] = []
    all_started = asyncio.Event()

    async def _fake_fetch_text(*, url: str, **_: object) -> str:
        started_urls.append(url)
        if len(started_urls) == 3:
            all_started.set()
        await all_started.wait()
        if "google" in url:
            return _GOOGLE_HTML
        if "bing" in url:
            return _BING_HTML
        return _DDG_HTML

    monkeypatch.setattr(http_client, "fetch_text", _fake_fetch_text)

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
