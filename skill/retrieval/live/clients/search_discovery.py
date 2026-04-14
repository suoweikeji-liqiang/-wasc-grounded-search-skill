"""Shared multi-engine discovery helpers for live adapters."""

from __future__ import annotations

import asyncio
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
    html = await http_client.fetch_text(
        url=config["url"],
        params=config["params"](query),
        timeout=2.0,
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
