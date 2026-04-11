"""Official policy registry adapter with deterministic fixture output."""

from __future__ import annotations

from skill.retrieval.models import RetrievalHit

_SOURCE_ID = "policy_official_registry"
_FIXTURES: tuple[dict[str, str], ...] = (
    {
        "title": "Ministry of Ecology and Environment policy bulletin",
        "url": "https://www.mee.gov.cn/policy/latest-regulation",
        "snippet": "Official regulatory bulletin for environmental compliance.",
    },
    {
        "title": "State Council administrative regulation repository update",
        "url": "https://www.gov.cn/zhengce/content/official-update.htm",
        "snippet": "Authoritative policy text with publication references.",
    },
)


def _score(query: str, fixture: dict[str, str]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((fixture["title"], fixture["snippet"])).lower()
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
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
        )
        for item in ranked
    ]
