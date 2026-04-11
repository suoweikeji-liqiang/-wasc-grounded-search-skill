"""Domain-first retrieval prioritization rules (D-15 through D-19)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from skill.retrieval.models import RetrievalHit

RouteLabel = Literal["policy", "industry", "academic", "mixed"]
ConcreteRoute = Literal["policy", "industry", "academic"]

_POLICY_SOURCE_PRIORITY: dict[str, int] = {
    "policy_official_registry": 0,
    "policy_official_web_allowlist_fallback": 1,
}
_ACADEMIC_ALLOWED_SOURCES: frozenset[str] = frozenset(
    {"academic_semantic_scholar", "academic_arxiv"}
)
_ACADEMIC_SOURCE_PRIORITY: dict[str, int] = {
    "academic_semantic_scholar": 0,
    "academic_arxiv": 1,
}
_INDUSTRY_TIER_PRIORITY: dict[str | None, int] = {
    "company_official": 0,
    "industry_association": 1,
    "trusted_news": 2,
    "general_web": 3,
    None: 4,
}
_DATE_PATTERN = re.compile(r"(20\d{2})[-_/](\d{2})[-_/](\d{2})")


def _route_for_hit(hit: RetrievalHit) -> ConcreteRoute | None:
    if hit.source_id.startswith("policy_"):
        return "policy"
    if hit.source_id.startswith("academic_"):
        return "academic"
    if hit.source_id.startswith("industry_"):
        return "industry"
    return None


def _recency_key(hit: RetrievalHit) -> int:
    haystack = f"{hit.url} {hit.title} {hit.snippet}"
    match = _DATE_PATTERN.search(haystack)
    if not match:
        return 0
    try:
        dt = datetime(
            year=int(match.group(1)),
            month=int(match.group(2)),
            day=int(match.group(3)),
        )
    except ValueError:
        return 0
    return dt.toordinal()


def _generic_relevance_key(hit: RetrievalHit) -> int:
    return len(hit.title) + len(hit.snippet)


def _sort_policy(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    indexed = list(enumerate(hits))
    ranked = sorted(
        indexed,
        key=lambda item: (
            -_POLICY_SOURCE_PRIORITY.get(item[1].source_id, 9),
            _recency_key(item[1]),
            _generic_relevance_key(item[1]),
            -item[0],
        ),
        reverse=True,
    )
    return [hit for _, hit in ranked]


def _sort_academic(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    scholarly_only = [hit for hit in hits if hit.source_id in _ACADEMIC_ALLOWED_SOURCES]
    indexed = list(enumerate(scholarly_only))
    ranked = sorted(
        indexed,
        key=lambda item: (
            -_ACADEMIC_SOURCE_PRIORITY.get(item[1].source_id, 9),
            _recency_key(item[1]),
            _generic_relevance_key(item[1]),
            -item[0],
        ),
        reverse=True,
    )
    return [hit for _, hit in ranked]


def _sort_industry(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    indexed = list(enumerate(hits))
    ranked = sorted(
        indexed,
        key=lambda item: (
            -_INDUSTRY_TIER_PRIORITY.get(item[1].credibility_tier, 99),
            _recency_key(item[1]),
            _generic_relevance_key(item[1]),
            -item[0],
        ),
        reverse=True,
    )
    return [hit for _, hit in ranked]


def _sort_by_route(route: ConcreteRoute, hits: list[RetrievalHit]) -> list[RetrievalHit]:
    if route == "policy":
        return _sort_policy(hits)
    if route == "academic":
        return _sort_academic(hits)
    return _sort_industry(hits)


def prioritize_hits(
    domain: str,
    hits: list[RetrievalHit],
    primary_route: str,
    supplemental_route: str | None,
) -> list[RetrievalHit]:
    """Apply hard domain rules before generic scoring (D-15)."""
    if not hits:
        return []

    if domain == "mixed":
        primary_hits = [hit for hit in hits if _route_for_hit(hit) == primary_route]
        supplemental_hits = [
            hit for hit in hits if _route_for_hit(hit) == supplemental_route
        ]
        other_hits = [
            hit
            for hit in hits
            if hit not in primary_hits and hit not in supplemental_hits
        ]
        ordered_primary = _sort_by_route(primary_route, primary_hits)  # type: ignore[arg-type]
        if supplemental_route is not None:
            ordered_supplemental = _sort_by_route(
                supplemental_route, supplemental_hits
            )  # type: ignore[arg-type]
        else:
            ordered_supplemental = []
        return ordered_primary + ordered_supplemental + other_hits

    if domain == "policy":
        return _sort_policy(hits)
    if domain == "academic":
        return _sort_academic(hits)
    if domain == "industry":
        return _sort_industry(hits)
    return _sort_by_route(primary_route, hits)  # type: ignore[arg-type]
