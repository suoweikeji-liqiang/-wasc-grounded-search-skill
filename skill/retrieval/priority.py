"""Domain-first retrieval prioritization rules (D-15 through D-19)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from skill.orchestrator.normalize import normalize_query_text, query_tokens
from skill.orchestrator.query_traits import derive_query_traits
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
_POLICY_CHANGE_MARKERS: tuple[str, ...] = (
    "\u4fee\u8ba2",
    "\u53d8\u5316",
    "\u4fee\u6b63",
    "amendment",
    "revision",
    "update",
)
_POLICY_EFFECTIVE_MARKERS: tuple[str, ...] = (
    "\u751f\u6548",
    "\u65bd\u884c",
    "\u5b9e\u65bd",
    "effective date",
)
_INDUSTRY_TREND_MARKERS: tuple[str, ...] = (
    "\u8d8b\u52bf",
    "\u9884\u6d4b",
    "\u51fa\u8d27",
    "\u4efd\u989d",
    "\u5e02\u573a",
    "trend",
    "forecast",
    "outlook",
    "shipment",
    "shipments",
    "share",
)
_IMPACT_MARKERS: tuple[str, ...] = (
    "\u5f71\u54cd",
    "\u843d\u5730",
    "\u6548\u5e94",
    "impact",
    "effect",
    "deployment",
)
_ACADEMIC_LOOKUP_MARKERS: tuple[str, ...] = (
    "\u8bba\u6587",
    "\u7814\u7a76",
    "\u7efc\u8ff0",
    "\u57fa\u51c6",
    "paper",
    "research",
    "study",
    "survey",
    "benchmark",
    "review",
)


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


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(normalize_query_text(marker) in text for marker in markers)


def _normalized_record_text(
    *,
    title: str,
    snippet: str,
    url: str,
    authority: str | None = None,
    publication_date: str | None = None,
    effective_date: str | None = None,
    version: str | None = None,
    year: int | None = None,
) -> str:
    parts = [
        title,
        snippet,
        url,
        authority or "",
        publication_date or "",
        effective_date or "",
        version or "",
        str(year) if year is not None else "",
    ]
    return normalize_query_text(" ".join(part for part in parts if part))


def score_query_alignment(
    query: str,
    *,
    route: ConcreteRoute,
    title: str,
    snippet: str,
    url: str,
    authority: str | None = None,
    publication_date: str | None = None,
    effective_date: str | None = None,
    version: str | None = None,
    year: int | None = None,
) -> int:
    normalized_query = normalize_query_text(query)
    normalized_record = _normalized_record_text(
        title=title,
        snippet=snippet,
        url=url,
        authority=authority,
        publication_date=publication_date,
        effective_date=effective_date,
        version=version,
        year=year,
    )
    query_token_set = tuple(dict.fromkeys(query_tokens(normalized_query)))
    record_token_set = set(query_tokens(normalized_record))
    query_year_tokens = {
        token for token in query_token_set if token.isdigit() and len(token) == 4
    }
    non_year_overlap = sum(
        1
        for token in query_token_set
        if token not in query_year_tokens and token in record_token_set
    )

    token_score = 0
    for token in query_token_set:
        if token not in record_token_set:
            continue
        if token.isdigit() and len(token) == 4:
            if non_year_overlap > 0:
                token_score += 4
        elif token.isascii() and len(token) >= 4:
            token_score += 2
        else:
            token_score += 1

    traits = derive_query_traits(query)
    route_bonus = 0
    if route == "policy":
        if traits.is_policy_change and _contains_any(normalized_record, _POLICY_CHANGE_MARKERS):
            route_bonus += 4
        if traits.has_version_intent and (version or _contains_any(normalized_record, _POLICY_CHANGE_MARKERS)):
            route_bonus += 3
        if traits.has_effective_date_intent and (
            effective_date or _contains_any(normalized_record, _POLICY_EFFECTIVE_MARKERS)
        ):
            route_bonus += 3
    elif route == "industry":
        if traits.has_trend_intent and _contains_any(normalized_record, _INDUSTRY_TREND_MARKERS):
            route_bonus += 4
        if (
            traits.has_year
            and query_year_tokens & record_token_set
            and (non_year_overlap > 0 or _contains_any(normalized_record, _INDUSTRY_TREND_MARKERS))
        ):
            route_bonus += 2
    else:
        if _contains_any(normalized_record, _ACADEMIC_LOOKUP_MARKERS):
            route_bonus += 2
        if traits.has_year and query_year_tokens & record_token_set and non_year_overlap > 0:
            route_bonus += 1

    if traits.is_cross_domain_impact and _contains_any(normalized_record, _IMPACT_MARKERS):
        route_bonus += 2

    return token_score + route_bonus


def _query_match_key(query: str, hit: RetrievalHit, *, route: ConcreteRoute) -> int:
    return score_query_alignment(
        query,
        route=route,
        title=hit.title,
        snippet=hit.snippet,
        url=hit.url,
        authority=hit.authority,
        publication_date=hit.publication_date,
        effective_date=hit.effective_date,
        version=hit.version,
        year=hit.year,
    )


def _sort_policy(hits: list[RetrievalHit], *, query: str | None = None) -> list[RetrievalHit]:
    indexed = list(enumerate(hits))
    ranked = sorted(
        indexed,
        key=lambda item: (
            _POLICY_SOURCE_PRIORITY.get(item[1].source_id, 9),
            -(_query_match_key(query, item[1], route="policy") if query is not None else 0),
            -_recency_key(item[1]),
            -_generic_relevance_key(item[1]),
            item[0],
        ),
    )
    return [hit for _, hit in ranked]


def _sort_academic(hits: list[RetrievalHit], *, query: str | None = None) -> list[RetrievalHit]:
    scholarly_only = [hit for hit in hits if hit.source_id in _ACADEMIC_ALLOWED_SOURCES]
    indexed = list(enumerate(scholarly_only))
    ranked = sorted(
        indexed,
        key=lambda item: (
            _ACADEMIC_SOURCE_PRIORITY.get(item[1].source_id, 9),
            -(_query_match_key(query, item[1], route="academic") if query is not None else 0),
            -_recency_key(item[1]),
            -_generic_relevance_key(item[1]),
            item[0],
        ),
    )
    return [hit for _, hit in ranked]


def _sort_industry(hits: list[RetrievalHit], *, query: str | None = None) -> list[RetrievalHit]:
    indexed = list(enumerate(hits))
    if query is not None:
        ranked = sorted(
            indexed,
            key=lambda item: (
                -_query_match_key(query, item[1], route="industry"),
                _INDUSTRY_TIER_PRIORITY.get(item[1].credibility_tier, 99),
                -_recency_key(item[1]),
                -_generic_relevance_key(item[1]),
                item[0],
            ),
        )
    else:
        ranked = sorted(
            indexed,
            key=lambda item: (
                _INDUSTRY_TIER_PRIORITY.get(item[1].credibility_tier, 99),
                -_recency_key(item[1]),
                -_generic_relevance_key(item[1]),
                item[0],
            ),
        )
    return [hit for _, hit in ranked]


def _sort_by_route(
    route: ConcreteRoute,
    hits: list[RetrievalHit],
    *,
    query: str | None = None,
) -> list[RetrievalHit]:
    if route == "policy":
        return _sort_policy(hits, query=query)
    if route == "academic":
        return _sort_academic(hits, query=query)
    return _sort_industry(hits, query=query)


def prioritize_hits(
    domain: str,
    hits: list[RetrievalHit],
    primary_route: str,
    supplemental_route: str | None,
    query: str | None = None,
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
        ordered_primary = _sort_by_route(
            primary_route,
            primary_hits,
            query=query,
        )  # type: ignore[arg-type]
        if supplemental_route is not None:
            ordered_supplemental = _sort_by_route(
                supplemental_route,
                supplemental_hits,
                query=query,
            )  # type: ignore[arg-type]
        else:
            ordered_supplemental = []
        return ordered_primary + ordered_supplemental + other_hits

    if domain == "policy":
        return _sort_policy(hits, query=query)
    if domain == "academic":
        return _sort_academic(hits, query=query)
    if domain == "industry":
        return _sort_industry(hits, query=query)
    return _sort_by_route(primary_route, hits, query=query)  # type: ignore[arg-type]
