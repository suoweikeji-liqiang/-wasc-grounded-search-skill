"""Fallback policy adapter constrained to official allowlisted domains."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlsplit

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.evidence.fact_density import rank_fact_paragraphs
from skill.retrieval.live.clients.browser_fetch import fetch_page_text
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.live.parsers.policy import (
    OFFICIAL_POLICY_ALLOWLIST,
    extract_policy_metadata,
    is_official_policy_url,
    preferred_policy_domains,
    preferred_policy_search_engines,
)
from skill.retrieval.models import RetrievalHit

SOURCE_ID = "policy_official_web_allowlist_fallback"
_SEARCH_TIMEOUT_SECONDS = 2.4
_SEARCH_MAX_RESULTS = 3
_CANDIDATE_LIMIT = 5
_PAGE_FETCH_TIMEOUT_SECONDS = 1.0
_SNIPPET_MAX_CHARS = 720

_RAW_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "State Council policy release",
        "url": "https://www.gov.cn/zhengce/official-release",
        "snippet": "Official policy release published on government domain.",
        "authority": "State Council",
        "jurisdiction": "CN",
        "publication_date": "2026-04-02",
        "effective_date": "2026-04-15",
    },
    {
        "title": "SAMR regulatory interpretation",
        "url": "https://www.samr.gov.cn/fgs/art/2026/4/11/art_1234.html",
        "snippet": "Regulator interpretation note tied to official rule text.",
        "authority": "State Administration for Market Regulation",
        "jurisdiction": "CN",
        "publication_date": "2026-04-11",
        "effective_date": "2026-04-20",
        "version": "2026-04-11 interpretation",
    },
    {
        "title": "Policy analysis blog post",
        "url": "https://blog.example.com/policy/hot-take",
        "snippet": "Secondary interpretation from a non-authoritative site.",
    },
)


def _detach_task(task: asyncio.Task[object]) -> None:
    def _consume_result(done_task: asyncio.Task[object]) -> None:
        try:
            done_task.result()
        except BaseException:
            return

    task.add_done_callback(_consume_result)


def _is_allowlisted(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host.lower() in OFFICIAL_POLICY_ALLOWLIST


def _score(query: str, fixture: dict[str, Any]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((str(fixture["title"]), str(fixture["snippet"]))).lower()
    return sum(1 for token in tokens if token in haystack)


def _query_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw_term in re.findall(r"[^\s]+", query.lower()):
        term = raw_term.strip(".,:;()[]{}\"'")
        if not term:
            continue
        if len(term) < 3 and not any(char.isdigit() for char in term):
            continue
        if term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return tuple(terms)


def _truncate_snippet(text: str, *, max_chars: int = _SNIPPET_MAX_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rstrip()
    last_break = max(truncated.rfind("\n\n"), truncated.rfind(". "), truncated.rfind("; "))
    if last_break >= max_chars // 2:
        truncated = truncated[:last_break].rstrip()
    return truncated


def _build_snippet(*, query: str, candidate_snippet: str, page_text: str) -> str:
    ranked = rank_fact_paragraphs(
        page_text,
        query_terms=_query_terms(query),
        limit=2,
        min_chars=40,
        max_chars=360,
        min_score=1.0,
    )
    if ranked:
        return _truncate_snippet("\n\n".join(item.text for item in ranked))
    if candidate_snippet:
        return _truncate_snippet(candidate_snippet.strip())
    if page_text:
        return _truncate_snippet(page_text[:_SNIPPET_MAX_CHARS].strip())
    return ""


async def search_fixture(query: str) -> list[RetrievalHit]:
    """Return deterministic allowlisted policy hits for offline tests."""
    allowlisted = [fixture for fixture in _RAW_FIXTURES if _is_allowlisted(fixture["url"])]
    ranked = sorted(
        allowlisted,
        key=lambda item: (_score(query, item), item["url"]),
        reverse=True,
    )
    return [
        RetrievalHit(
            source_id=SOURCE_ID,
            title=str(item["title"]),
            url=str(item["url"]),
            snippet=str(item["snippet"]),
            authority=str(item["authority"]),
            jurisdiction=str(item["jurisdiction"]),
            publication_date=str(item["publication_date"]),
            effective_date=str(item["effective_date"]),
            version=str(item["version"]) if item.get("version") is not None else None,
        )
        for item in ranked
    ]


async def _rank_candidate(
    *,
    query: str,
    candidate: Any,
    config: LiveRetrievalConfig,
) -> dict[str, Any] | None:
    if not is_official_policy_url(candidate.url):
        return None
    try:
        page_text = await fetch_page_text(
            url=candidate.url,
            browser_enabled=config.browser_enabled,
            browser_headless=config.browser_headless,
            timeout_seconds=_PAGE_FETCH_TIMEOUT_SECONDS,
            max_chars=1200,
        )
    except Exception:
        page_text = ""
    metadata = extract_policy_metadata(
        url=candidate.url,
        page_text="\n".join(
            part
            for part in (
                page_text,
                getattr(candidate, "title", ""),
                getattr(candidate, "snippet", ""),
                candidate.url,
            )
            if part
        ),
    )
    snippet = _build_snippet(
        query=query,
        candidate_snippet=getattr(candidate, "snippet", ""),
        page_text=page_text,
    )
    if metadata["authority"] is None or (
        metadata["publication_date"] is None
        and metadata["effective_date"] is None
        and _score(
            query,
            {
                "title": candidate.title,
                "snippet": snippet,
            },
        )
        <= 0
    ):
        return None
    return {
        "title": candidate.title,
        "url": candidate.url,
        "snippet": snippet,
        "authority": metadata["authority"],
        "jurisdiction": metadata["jurisdiction"],
        "publication_date": metadata["publication_date"],
        "effective_date": metadata["effective_date"],
        "version": metadata["version"],
        "_score": _score(
            query,
            {
                "title": candidate.title,
                "snippet": snippet,
            },
        ),
    }


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live allowlisted-policy hits from broader official discovery."""
    config = LiveRetrievalConfig.from_env()
    engines = preferred_policy_search_engines(config.search_engines)
    preferred_domains = preferred_policy_domains(query, fallback=True)
    async with asyncio.timeout(_SEARCH_TIMEOUT_SECONDS):
        try:
            search_results = await search_multi_engine(
                query=query,
                engines=engines,
                max_results=max(_SEARCH_MAX_RESULTS * 2, _CANDIDATE_LIMIT),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            search_results = []

        seen_urls: set[str] = set()
        candidates: list[Any] = []
        ranked_candidates = sorted(
            (
                candidate
                for candidate in search_results
                if is_official_policy_url(candidate.url)
            ),
            key=lambda candidate: (
                (
                    preferred_domains.index((urlsplit(candidate.url).hostname or "").lower())
                    if (urlsplit(candidate.url).hostname or "").lower() in preferred_domains
                    else 99
                ),
                candidate.url,
            ),
        )
        for item in ranked_candidates:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            candidates.append(item)
            if len(candidates) >= _CANDIDATE_LIMIT:
                break

        rank_tasks = [
            asyncio.create_task(
                _rank_candidate(
                    query=query,
                    candidate=candidate,
                    config=config,
                )
            )
            for candidate in candidates
        ]
        try:
            rank_results = await asyncio.gather(*rank_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            for task in rank_tasks:
                if not task.done():
                    task.cancel()
                _detach_task(task)
            raise
        ranked = [
            item
            for item in rank_results
            if not isinstance(item, Exception) and item is not None
        ]

        ranked.sort(key=lambda item: (item["_score"], item["url"]), reverse=True)
        return [
            RetrievalHit(
                source_id=SOURCE_ID,
                title=str(item["title"]),
                url=str(item["url"]),
                snippet=str(item["snippet"]),
                authority=str(item["authority"]) if item["authority"] is not None else None,
                jurisdiction=str(item["jurisdiction"]) if item["jurisdiction"] is not None else None,
                publication_date=str(item["publication_date"]) if item["publication_date"] is not None else None,
                effective_date=str(item["effective_date"]) if item["effective_date"] is not None else None,
                version=str(item["version"]) if item["version"] is not None else None,
            )
            for item in ranked[:5]
        ]


async def search(query: str) -> list[RetrievalHit]:
    """Backward-compatible deterministic adapter path for direct tests."""
    return await search_fixture(query)
