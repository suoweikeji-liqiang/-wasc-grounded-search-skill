"""Industry ddgs adapter with deterministic credibility-tier annotation."""

from __future__ import annotations

from urllib.parse import urlsplit

from skill.retrieval.models import RetrievalHit

SOURCE_ID = "industry_ddgs"
_TIER_ORDER: tuple[str, ...] = (
    "company_official",
    "industry_association",
    "trusted_news",
    "general_web",
)
_COMPANY_OFFICIAL_DOMAINS: frozenset[str] = frozenset(
    {"www.tesla.com", "www.byd.com"}
)
_INDUSTRY_ASSOCIATION_DOMAINS: frozenset[str] = frozenset(
    {"www.iea.org", "www.sae.org"}
)
_TRUSTED_NEWS_DOMAINS: frozenset[str] = frozenset(
    {"www.reuters.com", "www.bloomberg.com"}
)

_FIXTURES: tuple[dict[str, str], ...] = (
    {
        "title": "Tesla annual battery supply update",
        "url": "https://www.tesla.com/blog/battery-supply-update",
        "snippet": "Company disclosure on battery production guidance.",
    },
    {
        "title": "IEA outlook for battery manufacturing capacity",
        "url": "https://www.iea.org/reports/battery-manufacturing-2026",
        "snippet": "Industry-association market outlook and statistics.",
    },
    {
        "title": "Reuters report on EV battery pricing",
        "url": "https://www.reuters.com/world/asia-pacific/ev-battery-pricing-2026-04-10/",
        "snippet": "Trusted news coverage of supply chain price trends.",
    },
    {
        "title": "Community blog roundup of battery trends",
        "url": "https://analysis.example.net/battery-trends-roundup",
        "snippet": "General-web commentary on market sentiment.",
    },
)


def _tier_for_url(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    if host in _COMPANY_OFFICIAL_DOMAINS:
        return "company_official"
    if host in _INDUSTRY_ASSOCIATION_DOMAINS:
        return "industry_association"
    if host in _TRUSTED_NEWS_DOMAINS:
        return "trusted_news"
    return "general_web"


def _score(query: str, fixture: dict[str, str]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((fixture["title"], fixture["snippet"])).lower()
    return sum(1 for token in tokens if token in haystack)


async def search(query: str) -> list[RetrievalHit]:
    """Return industry hits annotated with deterministic credibility tiers."""
    ranked = sorted(
        _FIXTURES,
        key=lambda item: (
            -_TIER_ORDER.index(_tier_for_url(item["url"])),
            _score(query, item),
            item["url"],
        ),
        reverse=True,
    )
    return [
        RetrievalHit(
            source_id=SOURCE_ID,
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
            credibility_tier=_tier_for_url(item["url"]),
        )
        for item in ranked
    ]
