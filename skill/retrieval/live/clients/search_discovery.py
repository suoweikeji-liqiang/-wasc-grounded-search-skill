"""Shared multi-engine discovery helpers for live adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

from skill.retrieval.live.clients import http as http_client
from skill.orchestrator.normalize import normalize_query_text
from skill.retrieval.live.parsers.serp import (
    parse_bing_rss,
    parse_bing_html,
    parse_duckduckgo_html,
    parse_google_html,
    parse_google_news_rss,
)


@dataclass(frozen=True)
class SearchCandidate:
    engine: str
    title: str
    url: str
    snippet: str
    source_url: str = ""


_ENGINE_CONFIG = {
    "duckduckgo": {
        "url": "https://html.duckduckgo.com/html/",
        "params": lambda query: {"q": query},
        "parser": parse_duckduckgo_html,
        "timeout": 2.0,
        "max_chars": 120_000,
    },
    "bing": {
        "url": "https://www.bing.com/search",
        "params": lambda query: {"q": query},
        "parser": parse_bing_html,
        "timeout": 2.0,
        "max_chars": 120_000,
        "retry_attempts": 2,
    },
    "bing_rss": {
        "url": "https://www.bing.com/search",
        "params": lambda query: {"q": query, "format": "rss"},
        "parser": parse_bing_rss,
        "timeout": 3.0,
        "max_chars": 120_000,
        "retry_attempts": 3,
    },
    "google": {
        "url": "https://www.google.com/search",
        "params": lambda query: {"q": query, "hl": "en"},
        "parser": parse_google_html,
        "timeout": 2.0,
        "max_chars": 120_000,
    },
    "google_news_rss": {
        "url": "https://news.google.com/rss/search",
        "params": lambda query: {
            "q": query,
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        },
        "parser": parse_google_news_rss,
        "timeout": 3.0,
        "max_chars": 120_000,
    },
}


def _detach_task(task: asyncio.Task[object]) -> None:
    def _consume_result(done_task: asyncio.Task[object]) -> None:
        try:
            done_task.result()
        except BaseException:
            return

    task.add_done_callback(_consume_result)


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
    normalized_query = normalize_query_text(query)
    html = ""
    retry_attempts = max(1, int(config.get("retry_attempts", 1)))
    retryable_exceptions = (httpx.ConnectError, httpx.TimeoutException)
    for attempt in range(retry_attempts):
        try:
            html = await http_client.fetch_text_limited(
                url=config["url"],
                params=config["params"](query),
                timeout=float(config.get("timeout", 2.0)),
                max_chars=int(config.get("max_chars", 120_000)),
                cache_scope="search",
                cache_key=(
                    f"search:{engine}:{normalized_query}:chars={int(config.get('max_chars', 120_000))}"
                ),
            )
            break
        except retryable_exceptions:
            if attempt + 1 >= retry_attempts:
                raise
            await asyncio.sleep(0.15 * (attempt + 1))
    parser = config["parser"]
    parsed = parser(html)
    return [
        SearchCandidate(
            engine=engine,
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
            source_url=str(item.get("source_url", "")),
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
    tasks = {
        engine: asyncio.create_task(
            search_candidates(
                query=query,
                engine=engine,
                max_results=max_results,
            )
        )
        for engine in engines
    }
    try:
        results = await asyncio.gather(
            *(tasks[engine] for engine in engines),
            return_exceptions=True,
        )
    except asyncio.CancelledError:
        for task in tasks.values():
            if not task.done():
                task.cancel()
            _detach_task(task)
        raise

    for engine, result in zip(engines, results):
        if isinstance(result, Exception):
            continue
        candidates = result
        for candidate in candidates:
            canonical = _canonical_url(candidate.url)
            if canonical in seen:
                continue
            seen.add(canonical)
            deduped.append(candidate)
            if len(deduped) >= max_results:
                return deduped

    return deduped
