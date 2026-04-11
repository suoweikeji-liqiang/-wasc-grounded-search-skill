"""Fallback policy adapter constrained to official allowlisted domains."""

from __future__ import annotations

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

_RAW_FIXTURES: tuple[dict[str, str], ...] = (
    {
        "title": "State Council policy release",
        "url": "https://www.gov.cn/zhengce/official-release",
        "snippet": "Official policy release published on government domain.",
    },
    {
        "title": "SAMR regulatory interpretation",
        "url": "https://www.samr.gov.cn/fgs/art/2026/4/11/art_1234.html",
        "snippet": "Regulator interpretation note tied to official rule text.",
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


def _score(query: str, fixture: dict[str, str]) -> int:
    tokens = [token for token in query.lower().split() if token]
    haystack = " ".join((fixture["title"], fixture["snippet"])).lower()
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
            title=item["title"],
            url=item["url"],
            snippet=item["snippet"],
        )
        for item in ranked
    ]
