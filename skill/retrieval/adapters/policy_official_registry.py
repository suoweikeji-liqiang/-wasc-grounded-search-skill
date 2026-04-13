"""Official policy registry adapter with deterministic fixture output."""

from __future__ import annotations

from typing import Any

from skill.retrieval.models import RetrievalHit

_SOURCE_ID = "policy_official_registry"
_FIXTURES: tuple[dict[str, Any], ...] = (
    {
        "title": "Ministry of Ecology and Environment policy bulletin",
        "url": "https://www.mee.gov.cn/policy/latest-regulation",
        "snippet": "Official regulatory bulletin for environmental compliance.",
        "authority": "Ministry of Ecology and Environment",
        "jurisdiction": "CN",
        "publication_date": "2026-03-18",
        "effective_date": "2026-04-01",
        "version": "2026-03 bulletin",
    },
    {
        "title": "State Council administrative regulation repository update",
        "url": "https://www.gov.cn/zhengce/content/official-update.htm",
        "snippet": "Authoritative policy text with publication references.",
        "authority": "State Council",
        "jurisdiction": "CN",
        "publication_date": "2026-02-21",
        "effective_date": "2026-03-01",
    },
    {
        "title": "State Council autonomous driving pilot regulation",
        "url": "https://www.gov.cn/zhengce/autonomous-driving-pilot-regulation",
        "snippet": "Official autonomous driving pilot regulation sets 2026 compliance requirements for road testing.",
        "authority": "State Council",
        "jurisdiction": "CN",
        "publication_date": "2026-03-28",
        "effective_date": "2026-05-01",
        "version": "2026 pilot edition",
    },
    {
        "title": "Ministry of Commerce AI chip export controls notice",
        "url": "https://www.mofcom.gov.cn/article/ai-chip-export-controls-2026",
        "snippet": "Official AI chip export controls notice tightens 2026 licensing requirements for advanced accelerators.",
        "authority": "Ministry of Commerce",
        "jurisdiction": "CN",
        "publication_date": "2026-04-02",
        "effective_date": "2026-04-15",
        "version": "2026 export control notice",
    },
)


def _score(query: str, fixture: dict[str, Any]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((str(fixture["title"]), str(fixture["snippet"]))).lower()
    return sum(1 for token in tokens if token in haystack)


async def search(query: str) -> list[RetrievalHit]:
    """Return deterministic official-policy hits from registry-like fixtures."""
    ranked = sorted(
        _FIXTURES,
        key=lambda item: (_score(query, item), item["url"]),
        reverse=True,
    )
    return [
        RetrievalHit(
            source_id=_SOURCE_ID,
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
