"""Shared multi-engine discovery helpers for live adapters."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from skill.retrieval.live.clients import http as http_client
from skill.retrieval.live.parsers.serp import (
    parse_bing_html,
    parse_duckduckgo_html,
    parse_google_html,
)


@dataclass(frozen=True)
class SearchCandidate:
    engine: str
    title: str
    url: str
    snippet: str


_ENGINE_CONFIG = {
    "duckduckgo": {
        "url": "https://html.duckduckgo.com/html/",
        "params": lambda query: {"q": query},
        "parser": parse_duckduckgo_html,
    },
    "bing": {
        "url": "https://www.bing.com/search",
        "params": lambda query: {"q": query},
        "parser": parse_bing_html,
    },
    "google": {
        "url": "https://www.google.com/search",
        "params": lambda query: {"q": query, "hl": "en"},
        "parser": parse_google_html,
    },
}


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


async def search_candidates(
    *,
    query: str,
    engine: str,
    max_results: int = 5,
) -> list[SearchCandidate]:
    config = _ENGINE_CONFIG[engine]
    html = await http_client.fetch_text(
        url=config["url"],
        params=config["params"](query),
    )
    parser = config["parser"]
    parsed = parser(html)
    return [
        SearchCandidate(
            engine=engine,
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
        )
        for item in parsed[: max(1, max_results)]
    ]


async def search_multi_engine(
    *,
    query: str,
    engines: tuple[str, ...],
    max_results: int = 10,
) -> list[SearchCandidate]:
    deduped: list[SearchCandidate] = []
    seen: set[str] = set()

    for engine in engines:
        try:
            candidates = await search_candidates(
                query=query,
                engine=engine,
                max_results=max_results,
            )
        except Exception:
            continue
        for candidate in candidates:
            canonical = _canonical_url(candidate.url)
            if canonical in seen:
                continue
            seen.add(canonical)
            deduped.append(candidate)
            if len(deduped) >= max_results:
                return deduped

    return deduped
