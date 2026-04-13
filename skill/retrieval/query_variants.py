"""Bounded route-aware query variant generation for retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from skill.orchestrator.normalize import normalize_query_text
from skill.orchestrator.query_traits import QueryTraits, derive_query_traits

RouteLabel = Literal["policy", "industry", "academic", "mixed"]
ConcreteRoute = Literal["policy", "industry", "academic"]

MAX_QUERY_VARIANTS = 3
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_INDUSTRY_SHARE_MARKERS: tuple[str, ...] = (
    "\u4efd\u989d",
    "\u5e02\u5360\u7387",
    "\u5e02\u573a\u4efd\u989d",
    "share",
    "market share",
)
_INDUSTRY_FORECAST_MARKERS: tuple[str, ...] = (
    "\u8d8b\u52bf",
    "\u9884\u6d4b",
    "trend",
    "forecast",
    "outlook",
)


@dataclass(frozen=True)
class QueryVariant:
    query: str
    reason_code: str


def _uses_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _append_terms(query: str, *terms: str) -> str:
    normalized_query = normalize_query_text(query)
    missing_terms = [
        term
        for term in terms
        if term and normalize_query_text(term) not in normalized_query
    ]
    if not missing_terms:
        return query.strip()
    return f"{query.strip()} {' '.join(missing_terms)}".strip()


def _contains_any_marker(normalized_query: str, markers: tuple[str, ...]) -> bool:
    return any(normalize_query_text(marker) in normalized_query for marker in markers)


def _policy_candidates(
    query: str,
    traits: QueryTraits,
    *,
    route_label: RouteLabel,
    use_cjk: bool,
) -> list[QueryVariant]:
    candidates: list[QueryVariant] = []
    if route_label == "mixed":
        focus_terms = ("\u653f\u7b56", "\u76d1\u7ba1") if use_cjk else ("policy", "regulation")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *focus_terms),
                reason_code="policy_focus",
            )
        )

    if traits.is_policy_change or traits.has_version_intent:
        revision_terms = ("\u4fee\u8ba2", "\u53d8\u5316") if use_cjk else ("revision", "amendment")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *revision_terms),
                reason_code="policy_change",
            )
        )

    if traits.has_effective_date_intent or traits.has_year:
        effective_terms = ("\u751f\u6548", "\u65f6\u95f4") if use_cjk else ("effective date",)
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *effective_terms),
                reason_code="policy_effective_date",
            )
        )

    return candidates


def _industry_candidates(
    query: str,
    traits: QueryTraits,
    *,
    route_label: RouteLabel,
    use_cjk: bool,
) -> list[QueryVariant]:
    candidates: list[QueryVariant] = []
    normalized_query = normalize_query_text(query)
    has_share_language = _contains_any_marker(normalized_query, _INDUSTRY_SHARE_MARKERS)
    has_forecast_language = _contains_any_marker(normalized_query, _INDUSTRY_FORECAST_MARKERS)

    if route_label == "mixed":
        focus_terms = ("\u4ea7\u4e1a", "\u5e02\u573a") if use_cjk else ("industry", "market")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *focus_terms),
                reason_code="industry_focus",
            )
        )

    if (traits.has_trend_intent or traits.has_year) and not (
        has_share_language or has_forecast_language
    ):
        trend_terms = ("\u8d8b\u52bf", "\u9884\u6d4b") if use_cjk else ("trend", "forecast")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *trend_terms),
                reason_code="industry_trend",
            )
        )

    if traits.has_trend_intent and not has_share_language:
        share_terms = ("\u5e02\u573a", "\u4efd\u989d") if use_cjk else ("market", "share")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *share_terms),
                reason_code="industry_share",
            )
        )

    return candidates


def _academic_candidates(
    query: str,
    traits: QueryTraits,
    *,
    route_label: RouteLabel,
    use_cjk: bool,
) -> list[QueryVariant]:
    candidates: list[QueryVariant] = []
    if route_label == "mixed":
        focus_terms = ("\u8bba\u6587", "\u7814\u7a76") if use_cjk else ("paper", "research")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *focus_terms),
                reason_code="academic_focus",
            )
        )

    lookup_terms = ("\u8bba\u6587", "\u7814\u7a76") if use_cjk else ("paper", "research")
    candidates.append(
        QueryVariant(
            query=_append_terms(query, *lookup_terms),
            reason_code="academic_lookup",
        )
    )

    if traits.has_year:
        benchmark_terms = ("\u7efc\u8ff0", "\u57fa\u51c6") if use_cjk else ("survey", "benchmark")
        candidates.append(
            QueryVariant(
                query=_append_terms(query, *benchmark_terms),
                reason_code="academic_benchmark",
            )
        )

    return candidates


def build_query_variants(
    *,
    query: str,
    route_label: RouteLabel,
    primary_route: ConcreteRoute,
    supplemental_route: ConcreteRoute | None,
    target_route: ConcreteRoute,
    variant_limit: int = MAX_QUERY_VARIANTS,
) -> tuple[QueryVariant, ...]:
    del primary_route
    del supplemental_route

    limit = max(1, variant_limit)
    traits = derive_query_traits(query)
    use_cjk = _uses_cjk(query)
    candidates: list[QueryVariant] = [
        QueryVariant(query=query.strip(), reason_code="original")
    ]

    if target_route == "policy":
        candidates.extend(
            _policy_candidates(
                query,
                traits,
                route_label=route_label,
                use_cjk=use_cjk,
            )
        )
    elif target_route == "industry":
        candidates.extend(
            _industry_candidates(
                query,
                traits,
                route_label=route_label,
                use_cjk=use_cjk,
            )
        )
    else:
        candidates.extend(
            _academic_candidates(
                query,
                traits,
                route_label=route_label,
                use_cjk=use_cjk,
            )
        )

    deduped: list[QueryVariant] = []
    seen_queries: set[str] = set()
    for candidate in candidates:
        normalized_query = normalize_query_text(candidate.query)
        if not normalized_query or normalized_query in seen_queries:
            continue
        deduped.append(candidate)
        seen_queries.add(normalized_query)
        if len(deduped) >= limit:
            break

    return tuple(deduped)
