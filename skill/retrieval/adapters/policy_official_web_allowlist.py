"""Fallback policy adapter constrained to official allowlisted domains."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from skill.retrieval.models import RetrievalHit

SOURCE_ID = "policy_official_web_allowlist_fallback"
OFFICIAL_POLICY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "gov.cn",
        "www.gov.cn",
        "samr.gov.cn",
        "www.samr.gov.cn",
    }
)

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


async def search(query: str) -> list[RetrievalHit]:
    """Return hits from official-policy allowlisted domains only."""
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
