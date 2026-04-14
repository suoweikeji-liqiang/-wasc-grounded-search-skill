"""Fallback policy adapter constrained to official allowlisted domains."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from skill.config.live_retrieval import LiveRetrievalConfig
from skill.retrieval.live.clients.browser_fetch import fetch_page_text
from skill.retrieval.live.clients.search_discovery import search_multi_engine
from skill.retrieval.live.parsers.policy import (
    OFFICIAL_POLICY_ALLOWLIST,
    extract_policy_metadata,
    is_official_policy_url,
    preferred_policy_domains,
)
from skill.retrieval.models import RetrievalHit

SOURCE_ID = "policy_official_web_allowlist_fallback"

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


def _is_allowlisted(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return host.lower() in OFFICIAL_POLICY_ALLOWLIST


def _score(query: str, fixture: dict[str, Any]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((str(fixture["title"]), str(fixture["snippet"]))).lower()
    return sum(1 for token in tokens if token in haystack)


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


async def search_live(query: str) -> list[RetrievalHit]:
    """Return live allowlisted-policy hits from broader official discovery."""
    config = LiveRetrievalConfig.from_env()
    seen_urls: set[str] = set()
    candidates = []
    for domain in preferred_policy_domains(query, fallback=True):
        try:
            discovered = await search_multi_engine(
                query=f"{query} site:{domain}",
                engines=config.search_engines,
                max_results=4,
            )
        except Exception:
            continue
        for item in discovered:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            candidates.append(item)

    ranked = []
    for candidate in candidates:
        if not is_official_policy_url(candidate.url):
            continue
        try:
            page_text = await fetch_page_text(
                url=candidate.url,
                browser_enabled=config.browser_enabled,
                browser_headless=config.browser_headless,
                timeout_seconds=6.0,
                max_chars=1200,
            )
        except Exception:
            page_text = ""
        metadata = extract_policy_metadata(url=candidate.url, page_text=page_text)
        if metadata["authority"] is None or (
            metadata["publication_date"] is None and metadata["effective_date"] is None
        ):
            continue
        ranked.append(
            {
                "title": candidate.title,
                "url": candidate.url,
                "snippet": candidate.snippet or page_text[:320],
                "authority": metadata["authority"],
                "jurisdiction": metadata["jurisdiction"],
                "publication_date": metadata["publication_date"],
                "effective_date": metadata["effective_date"],
                "version": metadata["version"],
                "_score": _score(
                    query,
                    {
                        "title": candidate.title,
                        "snippet": candidate.snippet or page_text[:320],
                    },
                ),
            }
        )

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
